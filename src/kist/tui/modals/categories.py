"""Category form and manager modals."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select

from kist.core.config import load_library_config, save_library_config
from kist.core.database import PartsDatabase
from kist.models.config import CategoryDef

# Symbol templates that ship with kist
TEMPLATE_OPTIONS: list[tuple[str, str]] = [
    ("None", ""),
    ("Resistor", "resistor"),
    ("Capacitor", "capacitor"),
    ("Inductor", "inductor"),
]


class CategoryFormModal(ModalScreen[tuple[str, CategoryDef] | None]):
    """
    Form for creating or editing a single category definition.

    Dismiss result: ``(code, CategoryDef)`` on save, ``None`` on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        edit: tuple[str, CategoryDef] | None = None,
    ) -> None:
        super().__init__()
        self._edit = edit

    def compose(self) -> ComposeResult:
        editing = self._edit is not None
        title = "Edit Category" if editing else "New Category"

        with Vertical(id="catform-container"):
            yield Label(title, id="catform-title")
            # Category fields
            with Horizontal(classes="form-field"):
                yield Label("Code", classes="field-label")
                yield Input(
                    id="cat-code",
                    classes="field-value",
                    placeholder="e.g. OPTO",
                    disabled=editing,
                )
            with Horizontal(classes="form-field"):
                yield Label("Name", classes="field-label")
                yield Input(
                    id="cat-name",
                    classes="field-value",
                    placeholder="e.g. Optocouplers",
                )
            with Horizontal(classes="form-field"):
                yield Label("Ref Designator", classes="field-label")
                yield Input(
                    id="cat-refdes",
                    classes="field-value",
                    placeholder="e.g. U",
                )
            with Horizontal(classes="form-field"):
                yield Label("Key Specs", classes="field-label")
                yield Input(
                    id="cat-keyspecs",
                    classes="field-value",
                    placeholder="Comma-separated spec names",
                )
            with Horizontal(classes="form-field"):
                yield Label("Value Field", classes="field-label")
                yield Input(
                    id="cat-valuefield",
                    classes="field-value",
                    placeholder="Spec name for value generation",
                )
            with Horizontal(classes="form-field"):
                yield Label("Template", classes="field-label")
                yield Select(
                    TEMPLATE_OPTIONS,
                    id="cat-template",
                    classes="field-value",
                    prompt="Select template",
                )

            # Subcategories section -- fills remaining space
            with Vertical(classes="section", id="section-subcategories"):
                yield Label(
                    "No subcategories", id="subcat-empty", classes="empty-message"
                )
                yield DataTable(id="subcat-table")
                with Horizontal(id="subcat-actions"):
                    yield Input(
                        id="subcat-code",
                        placeholder="Code",
                        classes="field-value",
                    )
                    yield Input(
                        id="subcat-name",
                        placeholder="Name",
                        classes="field-value",
                    )
                    yield Button("Add", id="add-subcat", variant="default")

            # Action buttons
            with Horizontal(id="catform-buttons"):
                yield Button("Cancel", id="catform-cancel", variant="default")
                yield Button(
                    "Save" if editing else "Create",
                    id="catform-save",
                    variant="primary",
                )

    def on_mount(self) -> None:
        self.query_one("#section-subcategories").border_title = "Subcategories"

        table = self.query_one("#subcat-table", DataTable)
        table.add_columns("Code", "Name")
        table.show_header = True
        table.cursor_type = "row"
        table.display = False

        if self._edit is not None:
            code, cat = self._edit
            self._populate_from_edit(code, cat)

    def _populate_from_edit(self, code: str, cat: CategoryDef) -> None:
        """Fill form fields from an existing CategoryDef."""
        self.query_one("#cat-code", Input).value = code
        self.query_one("#cat-name", Input).value = cat.name
        self.query_one("#cat-refdes", Input).value = cat.refdes
        self.query_one("#cat-keyspecs", Input).value = ", ".join(cat.key_specs)

        if isinstance(cat.value_field, list):
            self.query_one("#cat-valuefield", Input).value = ", ".join(cat.value_field)
        elif cat.value_field:
            self.query_one("#cat-valuefield", Input).value = cat.value_field

        if cat.symbol_template:
            self.query_one("#cat-template", Select).value = cat.symbol_template

        for sub_code, sub_name in cat.subcategory_names.items():
            self._add_subcat_to_table(sub_code, sub_name)

    # -- Subcategory management ---

    def _add_subcat_to_table(self, code: str, name: str) -> None:
        table = self.query_one("#subcat-table", DataTable)
        table.add_row(code, name)
        self._update_subcat_empty()

    def _update_subcat_empty(self) -> None:
        table = self.query_one("#subcat-table", DataTable)
        empty = table.row_count == 0
        self.query_one("#subcat-empty").display = empty
        table.display = not empty

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-subcat":
            self._submit_subcat()
        elif event.button.id == "catform-save":
            self.action_save()
        elif event.button.id == "catform-cancel":
            self.action_cancel()

    def _submit_subcat(self) -> None:
        code_input = self.query_one("#subcat-code", Input)
        name_input = self.query_one("#subcat-name", Input)
        code = code_input.value.strip().upper()
        name = name_input.value.strip()
        if not code or not name:
            return
        self._add_subcat_to_table(code, name)
        code_input.value = ""
        name_input.value = ""
        code_input.focus()

    # -- Actions ---

    def action_save(self) -> None:
        code = self.query_one("#cat-code", Input).value.strip().upper()
        name = self.query_one("#cat-name", Input).value.strip()
        refdes = self.query_one("#cat-refdes", Input).value.strip()

        if not code or not name or not refdes:
            self.notify("Code, Name, and Ref Designator are required", severity="error")
            return

        key_specs_raw = self.query_one("#cat-keyspecs", Input).value.strip()
        key_specs = [s.strip() for s in key_specs_raw.split(",") if s.strip()]

        value_field_raw = self.query_one("#cat-valuefield", Input).value.strip()
        value_field: str | list[str] | None = None
        if value_field_raw:
            parts = [s.strip() for s in value_field_raw.split(",") if s.strip()]
            value_field = parts[0] if len(parts) == 1 else parts

        template_val = self.query_one("#cat-template", Select).value
        symbol_template = (
            str(template_val) if template_val != Select.BLANK and template_val else None
        )

        # Collect subcategories from table
        subcategory_names: dict[str, str] = {}
        table = self.query_one("#subcat-table", DataTable)
        for row_key in table.rows:
            row = table.get_row(row_key)
            subcategory_names[str(row[0])] = str(row[1])

        cat_def = CategoryDef(
            name=name,
            refdes=refdes,
            key_specs=key_specs,
            subcategory_names=subcategory_names,
            value_field=value_field,
            symbol_template=symbol_template,
        )
        self.dismiss((code, cat_def))

    def action_cancel(self) -> None:
        self.dismiss(None)


class CategoryManagerModal(ModalScreen):
    """
    Table of all library categories with CRUD operations.

    Changes are saved immediately to ``.kist/config.toml``.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("a", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("d", "delete", "Delete"),
    ]

    def __init__(self, library_path: Path) -> None:
        super().__init__()
        self._library_path = library_path

    def compose(self) -> ComposeResult:
        with Vertical(id="catmgr-container"):
            yield Label("Categories", id="catmgr-title")
            yield DataTable(id="catmgr-table")

    def on_mount(self) -> None:
        table = self.query_one("#catmgr-table", DataTable)
        table.add_columns("Code", "Name", "RefDes", "Key Specs", "Template")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._reload_table()

    def _reload_table(self) -> None:
        """Reload category data from the library config."""
        table = self.query_one("#catmgr-table", DataTable)
        table.clear()
        config = load_library_config(self._library_path)
        for code, cat in config.categories.items():
            specs = ", ".join(cat.key_specs) if cat.key_specs else ""
            template = cat.symbol_template or ""
            table.add_row(code, cat.name, cat.refdes, specs, template, key=code)

    def _selected_code(self) -> str | None:
        """Return the category code of the currently selected row."""
        table = self.query_one("#catmgr-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value)

    # -- Actions ---

    def action_add(self) -> None:
        self.app.push_screen(
            CategoryFormModal(),
            callback=self._on_form_result,
        )

    def action_edit(self) -> None:
        code = self._selected_code()
        if not code:
            return
        config = load_library_config(self._library_path)
        cat = config.categories.get(code)
        if not cat:
            return
        self.app.push_screen(
            CategoryFormModal(edit=(code, cat)),
            callback=self._on_form_result,
        )

    def _on_form_result(self, result: tuple[str, CategoryDef] | None) -> None:
        if result is None:
            return
        code, cat_def = result
        config = load_library_config(self._library_path)
        config.categories[code] = cat_def
        save_library_config(self._library_path, config)
        self._reload_table()

    def action_delete(self) -> None:
        code = self._selected_code()
        if not code:
            return

        # Warn if parts exist in this category
        db = PartsDatabase(self._library_path / "parts.json")
        db.load()
        count = sum(1 for p in db.list_parts() if p.category == code)
        if count:
            msg = f"Delete {code}? {count} part{'s' if count != 1 else ''} use this category."
        else:
            msg = f"Delete category {code}?"

        from kist.tui.screens.detail import ConfirmModal

        self.app.push_screen(
            ConfirmModal(msg),
            callback=lambda confirmed: self._on_delete_confirmed(confirmed, code),
        )

    def _on_delete_confirmed(self, confirmed: bool | None, code: str) -> None:
        if not confirmed:
            return
        config = load_library_config(self._library_path)
        config.categories.pop(code, None)
        save_library_config(self._library_path, config)
        self._reload_table()

    def action_close(self) -> None:
        self.dismiss()
