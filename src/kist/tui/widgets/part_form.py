"""PartForm -- single-page composite widget for viewing and editing parts."""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    Select,
    Static,
    TextArea,
)

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.models.part import (
    Mounting,
    Part,
    ProprietaryPart,
    SemiJellybeanPart,
    Tier,
)

# -- Select option lists ---

TIER_OPTIONS: list[tuple[str, str]] = [
    ("Proprietary", Tier.PROPRIETARY),
    ("Semi-jellybean", Tier.SEMI_JELLYBEAN),
    ("Jellybean", Tier.JELLYBEAN),
]

MOUNTING_OPTIONS: list[tuple[str, str]] = [
    ("SMD", Mounting.SMD),
    ("THT", Mounting.THT),
    ("Other", Mounting.OTHER),
]

CATEGORY_OPTIONS: list[tuple[str, str]] = [
    (f"{code} ({cat.name})", code) for code, cat in WELL_KNOWN_CATEGORIES.items()
]


def _subcategory_options(category: str) -> list[tuple[str, str]]:
    """Build subcategory select options for a given category code."""
    cat_def = WELL_KNOWN_CATEGORIES.get(category)
    if cat_def is None or not cat_def.subcategory_names:
        return []
    return [
        (f"{code} ({name})", code) for code, name in cat_def.subcategory_names.items()
    ]


# -- PartForm ---


class PartForm(Static):
    """
    Single-page form for viewing/editing a Part.

    Two modes: "editable" (inputs active) and "readonly" (labels shown).
    Layout: 2x2 grid -- General + Suppliers top, Specs + KiCad bottom.
    """

    def __init__(
        self,
        mode: Literal["editable", "readonly"] = "editable",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._mode: Literal["editable", "readonly"] = mode

    @property
    def mode(self) -> Literal["editable", "readonly"]:
        return self._mode

    @mode.setter
    def mode(self, value: Literal["editable", "readonly"]) -> None:
        self._mode = value
        if self.is_mounted:
            self._apply_mode()

    # -- Compose ---

    def compose(self) -> ComposeResult:
        with Horizontal(id="form-top"):
            yield from self._compose_general()
            yield from self._compose_supplier()
        with Horizontal(id="form-bottom"):
            yield from self._compose_kicad()
            yield from self._compose_specs()

    def _compose_general(self) -> ComposeResult:
        with Vertical(classes="section", id="section-general"):
            with Horizontal(classes="form-field"):
                yield Label("Tier", classes="field-label")
                yield Label("", id="tier-ro", classes="field-value-ro")
                yield Select(
                    TIER_OPTIONS, id="tier", classes="field-value", prompt="Select tier"
                )
            with Horizontal(classes="form-field"):
                yield Label("Category", classes="field-label")
                yield Label("", id="category-ro", classes="field-value-ro")
                yield Select(
                    CATEGORY_OPTIONS,
                    id="category",
                    classes="field-value",
                    prompt="Select category",
                )
            with Horizontal(classes="form-field"):
                yield Label("Subcategory", classes="field-label")
                yield Label("", id="subcategory-ro", classes="field-value-ro")
                yield Select(
                    [],
                    id="subcategory",
                    classes="field-value",
                    prompt="Select subcategory",
                )
            # MPN (tier-conditional)
            with Horizontal(classes="form-field", id="field-mpn"):
                yield Label("MPN", classes="field-label")
                yield Label("", id="mpn-ro", classes="field-value-ro")
                yield Input(
                    id="mpn",
                    classes="field-value",
                    placeholder="Manufacturer part number",
                )
            # Manufacturer (tier-conditional)
            with Horizontal(classes="form-field", id="field-manufacturer"):
                yield Label("Manufacturer", classes="field-label")
                yield Label("", id="manufacturer-ro", classes="field-value-ro")
                yield Input(
                    id="manufacturer", classes="field-value", placeholder="Manufacturer"
                )
            # Base PN (tier-conditional: semi-JB only)
            with Horizontal(classes="form-field", id="field-base-pn"):
                yield Label("Base PN", classes="field-label")
                yield Label("", id="base-pn-ro", classes="field-value-ro")
                yield Input(
                    id="base-pn",
                    classes="field-value",
                    placeholder="Base part number",
                )
            with Horizontal(classes="form-field"):
                yield Label("Package", classes="field-label")
                yield Label("", id="package-ro", classes="field-value-ro")
                yield Input(id="package", classes="field-value", placeholder="Package")
            with Horizontal(classes="form-field"):
                yield Label("Mounting", classes="field-label")
                yield Label("", id="mounting-ro", classes="field-value-ro")
                yield Select(
                    MOUNTING_OPTIONS,
                    id="mounting",
                    classes="field-value",
                    prompt="Select mounting",
                )
            # Name (always read-only)
            with Horizontal(classes="form-field"):
                yield Label("Name", classes="field-label")
                yield Label("", id="part-name-ro", classes="field-value-ro")
            with Horizontal(classes="form-field"):
                yield Label("Description", classes="field-label")
                yield Label("", id="description-ro", classes="field-value-ro")
                yield Input(
                    id="description", classes="field-value", placeholder="Description"
                )
            with Horizontal(classes="form-field"):
                yield Label("Tags", classes="field-label")
                yield Label("", id="tags-ro", classes="field-value-ro")
                yield Input(
                    id="tags",
                    classes="field-value",
                    placeholder="Comma-separated tags",
                )
            with Horizontal(classes="form-field"):
                yield Label("Datasheet", classes="field-label")
                yield Label("", id="datasheet-ro", classes="field-value-ro")
                yield Input(
                    id="datasheet",
                    classes="field-value",
                    placeholder="Datasheet URL",
                )
            yield Static("", classes="spacer")
            yield Label("Notes", classes="section-header")
            yield TextArea(id="notes")

    def _compose_supplier(self) -> ComposeResult:
        with Vertical(classes="section", id="section-supplier"):
            yield Label("No suppliers", id="suppliers-empty", classes="empty-message")
            yield DataTable(id="suppliers-table")
            with Horizontal(classes="form-actions", id="suppliers-actions"):
                yield Input(
                    id="supplier-name", placeholder="Supplier", classes="field-value"
                )
                yield Input(id="supplier-sku", placeholder="SKU", classes="field-value")
                yield Input(id="supplier-url", placeholder="URL", classes="field-value")
                yield Button("Add", id="add-supplier", variant="default", disabled=True)

    def _compose_kicad(self) -> ComposeResult:
        with Vertical(classes="section", id="section-kicad"):
            with Horizontal(classes="form-field"):
                yield Label("Symbol", classes="field-label")
                yield Label("", id="symbol-ro", classes="field-value-ro")
                yield Input(
                    id="symbol", classes="field-value", placeholder="Library:Symbol"
                )
            with Horizontal(classes="form-field"):
                yield Label("Footprint", classes="field-label")
                yield Label("", id="footprint-ro", classes="field-value-ro")
                yield Input(
                    id="footprint",
                    classes="field-value",
                    placeholder="Library:Footprint",
                )
            with Horizontal(classes="form-field"):
                yield Label("Keywords", classes="field-label")
                yield Label("", id="keywords-ro", classes="field-value-ro")
                yield Input(
                    id="keywords",
                    classes="field-value",
                    placeholder="Space-separated",
                )

    def _compose_specs(self) -> ComposeResult:
        with Vertical(classes="section", id="section-specs"):
            yield Label("No specs", id="specs-empty", classes="empty-message")
            yield DataTable(id="specs-table")
            with Horizontal(classes="form-actions", id="specs-actions"):
                yield Input(id="spec-key", placeholder="Key", classes="field-value")
                yield Input(id="spec-value", placeholder="Value", classes="field-value")
                yield Button(
                    "Add spec", id="add-spec", variant="default", disabled=True
                )

    # -- Mount ---

    def on_mount(self) -> None:
        # Section border titles
        self.query_one("#section-general").border_title = "General"
        self.query_one("#section-supplier").border_title = "Suppliers"
        self.query_one("#section-kicad").border_title = "KiCad"
        self.query_one("#section-specs").border_title = "Specs"

        # Specs table setup
        specs_table = self.query_one("#specs-table", DataTable)
        specs_table.add_columns("Key", "Value")
        specs_table.show_header = False
        specs_table.cursor_type = "row"
        specs_table.zebra_stripes = True
        specs_table.display = False
        specs_table.can_focus = False

        # Suppliers table setup
        sup_table = self.query_one("#suppliers-table", DataTable)
        sup_table.add_columns("Supplier", "SKU", "URL")
        sup_table.show_header = True
        sup_table.cursor_type = "row"
        sup_table.zebra_stripes = True
        sup_table.display = False
        sup_table.can_focus = False

        self._apply_mode()
        # Default tier visibility -- show all fields until a tier is selected
        self._apply_tier_visibility(None)

    # -- Mode switching ---

    # Widget pairs: (readonly label id, editable widget id)
    _RW_PAIRS: list[tuple[str, str]] = [
        ("tier-ro", "tier"),
        ("category-ro", "category"),
        ("subcategory-ro", "subcategory"),
        ("mpn-ro", "mpn"),
        ("manufacturer-ro", "manufacturer"),
        ("base-pn-ro", "base-pn"),
        ("package-ro", "package"),
        ("mounting-ro", "mounting"),
        ("description-ro", "description"),
        ("tags-ro", "tags"),
        ("symbol-ro", "symbol"),
        ("footprint-ro", "footprint"),
        ("keywords-ro", "keywords"),
        ("datasheet-ro", "datasheet"),
    ]

    def _apply_mode(self) -> None:
        """Toggle display on all readonly/editable widget pairs."""
        editable = self._mode == "editable"
        for ro_id, rw_id in self._RW_PAIRS:
            self.query_one(f"#{ro_id}").display = not editable
            self.query_one(f"#{rw_id}").display = editable

        self.query_one("#notes", TextArea).disabled = not editable
        # Action buttons hidden in readonly
        self.query_one("#specs-actions").display = editable
        self.query_one("#suppliers-actions").display = editable

    # -- Tier visibility ---

    def _apply_tier_visibility(self, tier: str | None) -> None:
        """Show/hide fields based on the selected tier."""
        show_mpn = tier in (Tier.PROPRIETARY, Tier.SEMI_JELLYBEAN)
        show_base_pn = tier == Tier.SEMI_JELLYBEAN

        self.query_one("#field-mpn").display = show_mpn
        self.query_one("#field-manufacturer").display = show_mpn
        self.query_one("#field-base-pn").display = show_base_pn

    # -- Category cascading ---

    def _update_subcategories(self, category: str) -> None:
        """Update subcategory select options based on category."""
        options = _subcategory_options(category)
        sub_select = self.query_one("#subcategory", Select)
        sub_select.set_options(options)

    # -- Event handlers ---

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "tier" and event.value != Select.BLANK:
            self._apply_tier_visibility(str(event.value))
        elif event.select.id == "category" and event.value != Select.BLANK:
            self._update_subcategories(str(event.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Enable Add buttons when required inputs have content."""
        if event.input.id == "spec-key":
            self.query_one("#add-spec", Button).disabled = not event.value.strip()
        elif event.input.id == "supplier-name":
            has_name = bool(event.value.strip())
            has_sku = bool(self.query_one("#supplier-sku", Input).value.strip())
            self.query_one("#add-supplier", Button).disabled = not (
                has_name and has_sku
            )
        elif event.input.id == "supplier-sku":
            has_name = bool(self.query_one("#supplier-name", Input).value.strip())
            has_sku = bool(event.value.strip())
            self.query_one("#add-supplier", Button).disabled = not (
                has_name and has_sku
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Tab through input fields, submit on last."""
        if event.input.id == "spec-key" and event.value.strip():
            self.query_one("#spec-value", Input).focus()
        elif event.input.id == "spec-value":
            if self.query_one("#spec-key", Input).value.strip():
                self._submit_spec()
        elif event.input.id == "supplier-name" and event.value.strip():
            self.query_one("#supplier-sku", Input).focus()
        elif event.input.id == "supplier-sku" and event.value.strip():
            self.query_one("#supplier-url", Input).focus()
        elif event.input.id == "supplier-url":
            if self.query_one("#supplier-name", Input).value.strip():
                self._submit_supplier()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-spec":
            self._submit_spec()
        elif event.button.id == "add-supplier":
            self._submit_supplier()

    # -- Spec management ---

    def _submit_spec(self) -> None:
        """Add spec from inputs to table, clear inputs, refocus key."""
        key_input = self.query_one("#spec-key", Input)
        value_input = self.query_one("#spec-value", Input)
        key = key_input.value.strip()
        value = value_input.value.strip()
        if not key:
            return
        self._add_spec_to_table(key, value)
        key_input.value = ""
        value_input.value = ""
        key_input.focus()

    def _add_spec_to_table(self, key: str, value: str) -> None:
        table = self.query_one("#specs-table", DataTable)
        table.add_row(key, value)
        self._update_specs_empty()

    def _delete_spec_row(self) -> None:
        """Remove the currently selected spec row (backspace from table)."""
        table = self.query_one("#specs-table", DataTable)
        if table.row_count > 0:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            table.remove_row(row_key)
            self._update_specs_empty()

    def _update_specs_empty(self) -> None:
        table = self.query_one("#specs-table", DataTable)
        empty = table.row_count == 0
        self.query_one("#specs-empty").display = empty
        table.display = not empty
        table.can_focus = not empty

    # -- Supplier management ---

    def _submit_supplier(self) -> None:
        """Add supplier from inputs to table, clear inputs, refocus name."""
        name_input = self.query_one("#supplier-name", Input)
        sku_input = self.query_one("#supplier-sku", Input)
        url_input = self.query_one("#supplier-url", Input)
        name = name_input.value.strip()
        sku = sku_input.value.strip()
        url = url_input.value.strip()
        if not name or not sku:
            return
        self._add_supplier_to_table(name, sku, url)
        name_input.value = ""
        sku_input.value = ""
        url_input.value = ""
        name_input.focus()

    def _add_supplier_to_table(self, name: str, sku: str, url: str) -> None:
        table = self.query_one("#suppliers-table", DataTable)
        table.add_row(name, sku, url)
        self._update_suppliers_empty()

    def _update_suppliers_empty(self) -> None:
        table = self.query_one("#suppliers-table", DataTable)
        empty = table.row_count == 0
        self.query_one("#suppliers-empty").display = empty
        table.display = not empty
        table.can_focus = not empty

    # -- Data flow ---

    def load_part(self, part: Part) -> None:
        """Populate all form fields from a Part model."""
        # Identity
        self.query_one("#tier", Select).value = part.tier
        self.query_one("#tier-ro", Label).update(part.tier.value)

        self.query_one("#category", Select).value = part.category
        cat_def = WELL_KNOWN_CATEGORIES.get(part.category)
        cat_label = f"{part.category} ({cat_def.name})" if cat_def else part.category
        self.query_one("#category-ro", Label).update(cat_label)

        self._update_subcategories(part.category)
        if part.subcategory:
            self.query_one("#subcategory", Select).value = part.subcategory
            sub_name = (
                cat_def.subcategory_names.get(part.subcategory, "") if cat_def else ""
            )
            sub_label = (
                f"{part.subcategory} ({sub_name})" if sub_name else part.subcategory
            )
            self.query_one("#subcategory-ro", Label).update(sub_label)

        if isinstance(part, (ProprietaryPart, SemiJellybeanPart)):
            self.query_one("#mpn", Input).value = part.mpn
            self.query_one("#mpn-ro", Label).update(part.mpn)
            self.query_one("#manufacturer", Input).value = part.manufacturer
            self.query_one("#manufacturer-ro", Label).update(part.manufacturer)

        if isinstance(part, SemiJellybeanPart):
            self.query_one("#base-pn", Input).value = part.base_pn
            self.query_one("#base-pn-ro", Label).update(part.base_pn)

        self.query_one("#package", Input).value = part.package or ""
        self.query_one("#package-ro", Label).update(part.package or "")

        if part.mounting:
            self.query_one("#mounting", Select).value = part.mounting
            self.query_one("#mounting-ro", Label).update(part.mounting.value)

        self.query_one("#part-name-ro", Label).update(part.name)

        self.query_one("#description", Input).value = part.description
        self.query_one("#description-ro", Label).update(part.description)

        tags_str = ", ".join(part.tags)
        self.query_one("#tags", Input).value = tags_str
        self.query_one("#tags-ro", Label).update(tags_str)

        # Tier visibility
        self._apply_tier_visibility(part.tier)

        # Specs
        if part.specifications:
            for key, val in part.specifications.items():
                self._add_spec_to_table(key, val)

        # Suppliers
        for sup_name, info in part.suppliers.items():
            url_str = str(info.url) if info.url else ""
            self._add_supplier_to_table(sup_name, info.sku, url_str)

        # KiCad
        self.query_one("#symbol", Input).value = part.symbol
        self.query_one("#symbol-ro", Label).update(part.symbol)
        self.query_one("#footprint", Input).value = part.footprint
        self.query_one("#footprint-ro", Label).update(part.footprint)

        keywords_str = " ".join(part.keywords)
        self.query_one("#keywords", Input).value = keywords_str
        self.query_one("#keywords-ro", Label).update(keywords_str)

        # Notes
        if part.datasheet:
            ds_str = str(part.datasheet)
            self.query_one("#datasheet", Input).value = ds_str
            self.query_one("#datasheet-ro", Label).update(ds_str)

        self.query_one("#notes", TextArea).text = part.notes or ""

    def to_dict(self) -> dict:
        """Extract current form values as a flat dict."""
        result: dict = {}

        # Identity
        tier_val = self.query_one("#tier", Select).value
        result["tier"] = tier_val if tier_val != Select.BLANK else None

        cat_val = self.query_one("#category", Select).value
        result["category"] = cat_val if cat_val != Select.BLANK else None

        sub_val = self.query_one("#subcategory", Select).value
        result["subcategory"] = sub_val if sub_val != Select.BLANK else None

        result["mpn"] = self.query_one("#mpn", Input).value
        result["manufacturer"] = self.query_one("#manufacturer", Input).value
        result["base_pn"] = self.query_one("#base-pn", Input).value
        result["package"] = self.query_one("#package", Input).value

        mounting_val = self.query_one("#mounting", Select).value
        result["mounting"] = mounting_val if mounting_val != Select.BLANK else None

        result["description"] = self.query_one("#description", Input).value

        tags_raw = self.query_one("#tags", Input).value
        result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

        # Specs
        specs: dict[str, str] = {}
        specs_table = self.query_one("#specs-table", DataTable)
        for row_key in specs_table.rows:
            row_data = specs_table.get_row(row_key)
            k = str(row_data[0]).strip()
            v = str(row_data[1]).strip()
            if k:
                specs[k] = v
        result["specifications"] = specs if specs else None

        # Suppliers
        suppliers: dict = {}
        sup_table = self.query_one("#suppliers-table", DataTable)
        for row_key in sup_table.rows:
            row_data = sup_table.get_row(row_key)
            sup_name = str(row_data[0]).strip()
            sku = str(row_data[1]).strip()
            url = str(row_data[2]).strip()
            if sup_name and sku:
                suppliers[sup_name] = {"sku": sku, "url": url or None}
        result["suppliers"] = suppliers

        # KiCad
        result["symbol"] = self.query_one("#symbol", Input).value
        result["footprint"] = self.query_one("#footprint", Input).value
        result["keywords"] = self.query_one("#keywords", Input).value.split()
        # Notes
        result["datasheet"] = self.query_one("#datasheet", Input).value or None
        result["notes"] = self.query_one("#notes", TextArea).text or None

        return result
