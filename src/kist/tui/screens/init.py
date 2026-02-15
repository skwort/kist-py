"""Init screen -- interactive library creation wizard."""

from __future__ import annotations

from pathlib import Path

from textual import getters
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Input, Label

from kist import __version__
from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.config import resolve_init_config
from kist.errors import LibraryExistsError
from kist.models.config import CategoryDef
from kist.tui.app import KistApp
from kist.tui.widgets.header import KistHeader


class InitScreen(Screen):
    """
    Full-screen wizard for creating a new kist library.

    Categories are held in local state until the user clicks Create.
    No library exists on disk until then.
    """

    app = getters.app(KistApp)

    TITLE = "Kist"
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "create", "Create"),
    ]

    def __init__(
        self,
        init_path: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._init_path = init_path or Path.cwd()
        self._categories: dict[str, CategoryDef] = dict(WELL_KNOWN_CATEGORIES)

    def compose(self) -> ComposeResult:
        yield KistHeader(icon="\N{PACKAGE}", page_title="Init Library")
        with VerticalScroll(id="init-scroll"):
            # Location section
            with Vertical(classes="section", id="section-location"):
                with Horizontal(classes="form-field"):
                    yield Label("Path", classes="field-label")
                    yield Input(
                        id="init-path",
                        classes="field-value",
                    )

            # Library section
            with Vertical(classes="section", id="section-init-library"):
                with Horizontal(classes="form-field"):
                    yield Label("Prefix", classes="field-label")
                    yield Input(
                        id="init-prefix",
                        classes="field-value",
                    )
                with Horizontal(classes="form-field"):
                    yield Label("Separator", classes="field-label")
                    yield Input(
                        id="init-separator",
                        classes="field-value",
                    )
                with Horizontal(classes="form-field"):
                    yield Label("Suppliers", classes="field-label")
                    yield Input(
                        id="init-suppliers",
                        classes="field-value",
                        placeholder="Comma-separated",
                    )

            # Directories section
            with Vertical(classes="section", id="section-init-dirs"):
                with Horizontal(classes="form-field"):
                    yield Label("Symbols", classes="field-label")
                    yield Input(id="init-symbols-dir", classes="field-value")
                with Horizontal(classes="form-field"):
                    yield Label("Footprints", classes="field-label")
                    yield Input(id="init-footprints-dir", classes="field-value")
                with Horizontal(classes="form-field"):
                    yield Label("3D Models", classes="field-label")
                    yield Input(id="init-models-dir", classes="field-value")
                with Horizontal(classes="form-field"):
                    yield Label("Blocks", classes="field-label")
                    yield Input(id="init-blocks-dir", classes="field-value")

            # Categories section
            with Vertical(classes="section", id="section-init-categories"):
                yield DataTable(id="init-cat-table")
                with Horizontal(id="init-cat-actions"):
                    yield Button("Add", id="init-cat-add", variant="default")
                    yield Button("Edit", id="init-cat-edit", variant="default")
                    yield Button("Delete", id="init-cat-delete", variant="default")

            # Action buttons
            with Horizontal(id="init-buttons"):
                yield Button("Cancel", id="init-cancel", variant="default")
                yield Button("Create", id="init-create", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#section-location").border_title = "Location"
        self.query_one("#section-init-library").border_title = "Library"
        self.query_one("#section-init-dirs").border_title = "Directories"
        self.query_one(
            "#section-init-categories"
        ).border_title = (
            "Categories  [dim]a[/dim]dd  [dim]e[/dim]dit  [dim]d[/dim]elete"
        )

        # Seed defaults from global config
        defaults = resolve_init_config()
        self.query_one("#init-path", Input).value = str(self._init_path)
        self.query_one("#init-prefix", Input).value = defaults.library_prefix
        self.query_one("#init-separator", Input).value = defaults.separator
        self.query_one("#init-suppliers", Input).value = ", ".join(defaults.suppliers)
        self.query_one("#init-symbols-dir", Input).value = defaults.symbols_dir
        self.query_one("#init-footprints-dir", Input).value = defaults.footprints_dir
        self.query_one("#init-models-dir", Input).value = defaults.models_dir
        self.query_one("#init-blocks-dir", Input).value = defaults.blocks_dir

        # Set up category table
        table = self.query_one("#init-cat-table", DataTable)
        table.add_columns("Code", "Name", "RefDes", "Key Specs", "Template")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._reload_categories()

    # -- Category table ---

    def _reload_categories(self) -> None:
        """Rebuild the category table from local state."""
        table = self.query_one("#init-cat-table", DataTable)
        table.clear()
        for code, cat in self._categories.items():
            specs = ", ".join(cat.key_specs) if cat.key_specs else ""
            template = cat.symbol_template or ""
            table.add_row(code, cat.name, cat.refdes, specs, template, key=code)

    def _selected_category_code(self) -> str | None:
        """Return the category code of the currently selected row."""
        table = self.query_one("#init-cat-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value)

    # -- Category CRUD via keybindings ---

    def on_key(self, event) -> None:
        """Handle a/e/d keys for category management when table is focused."""
        table = self.query_one("#init-cat-table", DataTable)
        if not table.has_focus:
            return

        if event.key == "a":
            event.prevent_default()
            self._add_category()
        elif event.key == "e":
            event.prevent_default()
            self._edit_category()
        elif event.key == "d":
            event.prevent_default()
            self._delete_category()

    def _add_category(self) -> None:
        from kist.tui.modals.categories import CategoryFormModal

        self.app.push_screen(
            CategoryFormModal(),
            callback=self._on_category_form_result,
        )

    def _edit_category(self) -> None:
        code = self._selected_category_code()
        if not code:
            return
        cat = self._categories.get(code)
        if not cat:
            return

        from kist.tui.modals.categories import CategoryFormModal

        self.app.push_screen(
            CategoryFormModal(edit=(code, cat)),
            callback=self._on_category_form_result,
        )

    def _on_category_form_result(self, result: tuple[str, CategoryDef] | None) -> None:
        if result is None:
            return
        code, cat_def = result
        self._categories[code] = cat_def
        self._reload_categories()

    def _delete_category(self) -> None:
        code = self._selected_category_code()
        if not code:
            return
        self._categories.pop(code, None)
        self._reload_categories()

    # -- Button handlers ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "init-create":
            self.action_create()
        elif event.button.id == "init-cancel":
            self.action_cancel()
        elif event.button.id == "init-cat-add":
            self._add_category()
        elif event.button.id == "init-cat-edit":
            self._edit_category()
        elif event.button.id == "init-cat-delete":
            self._delete_category()

    # -- Actions ---

    def action_create(self) -> None:
        """Validate inputs and create the library on disk."""
        from kist.core.library import init_library

        path_str = self.query_one("#init-path", Input).value.strip()
        if not path_str:
            self.notify("Path is required", severity="error")
            return

        path = Path(path_str).expanduser()
        prefix = self.query_one("#init-prefix", Input).value.strip()
        separator = self.query_one("#init-separator", Input).value.strip()
        suppliers_raw = self.query_one("#init-suppliers", Input).value.strip()
        suppliers = [s.strip() for s in suppliers_raw.split(",") if s.strip()]

        symbols_dir = self.query_one("#init-symbols-dir", Input).value.strip()
        footprints_dir = self.query_one("#init-footprints-dir", Input).value.strip()
        models_dir = self.query_one("#init-models-dir", Input).value.strip()
        blocks_dir = self.query_one("#init-blocks-dir", Input).value.strip()

        try:
            root = init_library(
                path,
                symbols_dir=symbols_dir or None,
                footprints_dir=footprints_dir or None,
                models_dir=models_dir or None,
                blocks_dir=blocks_dir or None,
                library_prefix=prefix or None,
                separator=separator or None,
                suppliers=suppliers or None,
                categories=self._categories,
            )
        except LibraryExistsError as exc:
            self.notify(str(exc), severity="error")
            return
        except Exception as exc:
            self.notify(f"Init failed: {exc}", severity="error")
            return

        # Point the app at the new library
        from kist.core.config import load_library_config

        self.app.library_path = root
        self.app.library_config = load_library_config(root)
        self.notify(f"Created library at {root}")
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()
