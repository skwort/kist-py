"""PartForm widget tests -- mode switching, tier visibility, data flow."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Label, Select

from kist.core.config import load_library_config, save_library_config
from kist.models.config import CategoryDef, LibraryConfig
from kist.models.part import (
    Mounting,
    ProprietaryPart,
    SupplierInfo,
    Tier,
)
from kist.tui.app import KistApp
from kist.tui.widgets.part_form import _NEW_CATEGORY, PartForm


class PartFormApp(App):
    """Minimal app for testing PartForm in isolation."""

    CSS = ""

    def __init__(self, mode="editable"):
        super().__init__()
        self._mode = mode

    def compose(self) -> ComposeResult:
        yield PartForm(mode=self._mode, id="form")


@pytest.fixture
def editable_app():
    return PartFormApp(mode="editable")


@pytest.fixture
def readonly_app():
    return PartFormApp(mode="readonly")


# -- Mode tests ---


async def test_editable_mode_shows_inputs(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        # Editable widget visible
        assert form.query_one("#tier", Select).display is True
        # Readonly label hidden
        assert form.query_one("#tier-ro", Label).display is False
        # Input visible
        assert form.query_one("#description", Input).display is True
        assert form.query_one("#description-ro", Label).display is False


async def test_readonly_mode_shows_labels(readonly_app):
    async with readonly_app.run_test():
        form = readonly_app.query_one("#form", PartForm)
        # Readonly label visible
        assert form.query_one("#tier-ro", Label).display is True
        # Editable widget hidden
        assert form.query_one("#tier", Select).display is False
        assert form.query_one("#description-ro", Label).display is True
        assert form.query_one("#description", Input).display is False


async def test_mode_toggle(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        assert form.mode == "editable"
        assert form.query_one("#tier", Select).display is True

        form.mode = "readonly"
        assert form.query_one("#tier", Select).display is False
        assert form.query_one("#tier-ro", Label).display is True

        form.mode = "editable"
        assert form.query_one("#tier", Select).display is True
        assert form.query_one("#tier-ro", Label).display is False


# -- Tier visibility tests ---


async def test_jellybean_hides_mpn_manufacturer_basepn(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._apply_tier_visibility(Tier.JELLYBEAN)

        assert form.query_one("#field-mpn").display is False
        assert form.query_one("#field-manufacturer").display is False
        assert form.query_one("#field-base-pn").display is False


async def test_semi_jellybean_shows_all_conditional_fields(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._apply_tier_visibility(Tier.SEMI_JELLYBEAN)

        assert form.query_one("#field-mpn").display is True
        assert form.query_one("#field-manufacturer").display is True
        assert form.query_one("#field-base-pn").display is True


async def test_proprietary_shows_mpn_hides_basepn(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._apply_tier_visibility(Tier.PROPRIETARY)

        assert form.query_one("#field-mpn").display is True
        assert form.query_one("#field-manufacturer").display is True
        assert form.query_one("#field-base-pn").display is False


# -- Category cascading ---


async def test_category_cascading_populates_subcategories(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._update_subcategories("CAP")

        sub_select = form.query_one("#subcategory", Select)
        # _options is a list of (label, value) tuples
        option_values = [opt[1] for opt in sub_select._options]
        assert "CER" in option_values
        assert "ELEC" in option_values
        assert "TANT" in option_values
        assert "FILM" in option_values


async def test_category_without_subcategories_clears_options(editable_app):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._update_subcategories("CAP")
        form._update_subcategories("IC")

        sub_select = form.query_one("#subcategory", Select)
        # Filter out the BLANK sentinel that Select always includes
        option_values = [
            opt[1] for opt in sub_select._options if opt[1] != Select.BLANK
        ]
        assert option_values == []


# -- load_part / to_dict roundtrip ---


async def test_load_part_to_dict_roundtrip(editable_app):
    part = ProprietaryPart(
        tier=Tier.PROPRIETARY,
        name="IC-STM32F405RGT6",
        description="ARM Cortex-M4 MCU",
        category="IC",
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        package="LQFP64",
        mounting=Mounting.SMD,
        tags=["mcu", "arm"],
        symbol="00k-ICs:IC-STM32F405",
        footprint="Package_QFP:LQFP-64",
        value="STM32F405RGT6",
        reference="U",
        keywords=["arm", "cortex"],
        specifications={"frequency": "168MHz", "flash": "1MB"},
        suppliers={"DigiKey": SupplierInfo(sku="497-STM32F405RGT6-ND")},
        exclude_from_bom=False,
        exclude_from_board=False,
    )

    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form.load_part(part)
        d = form.to_dict()

        assert d["tier"] == Tier.PROPRIETARY
        assert d["category"] == "IC"
        assert d["mpn"] == "STM32F405RGT6"
        assert d["manufacturer"] == "STMicroelectronics"
        assert d["package"] == "LQFP64"
        assert d["mounting"] == Mounting.SMD
        assert d["description"] == "ARM Cortex-M4 MCU"
        assert d["tags"] == ["mcu", "arm"]
        assert d["specifications"] == {"frequency": "168MHz", "flash": "1MB"}
        assert "DigiKey" in d["suppliers"]
        assert d["suppliers"]["DigiKey"]["sku"] == "497-STM32F405RGT6-ND"
        assert d["symbol"] == "00k-ICs:IC-STM32F405"
        assert d["footprint"] == "Package_QFP:LQFP-64"
        assert d["keywords"] == ["arm", "cortex"]


async def test_symbol_selection_applies_linked_footprint(editable_app, monkeypatch):
    monkeypatch.setattr("kist.kicad.discovery.detect_kicad", lambda: object())
    monkeypatch.setattr(
        "kist.kicad.indexer.linked_footprint_for_symbol",
        lambda *args, **kwargs: "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    )

    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._on_library_search_result("Regulator_Current:HV100K5-G", "symbol")

        assert form.query_one("#symbol", Input).value == "Regulator_Current:HV100K5-G"
        assert (
            form.query_one("#footprint", Input).value
            == "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
        )


async def test_symbol_selection_keeps_footprint_when_unlinked(
    editable_app, monkeypatch
):
    monkeypatch.setattr("kist.kicad.discovery.detect_kicad", lambda: object())
    monkeypatch.setattr(
        "kist.kicad.indexer.linked_footprint_for_symbol",
        lambda *args, **kwargs: None,
    )

    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form.query_one("#footprint", Input).value = "Existing:Footprint"

        form._on_library_search_result("Device_RCL:R", "symbol")

        assert form.query_one("#symbol", Input).value == "Device_RCL:R"
        assert form.query_one("#footprint", Input).value == "Existing:Footprint"


async def test_clone_symbol_selection_fills_original_footprint(
    editable_app, monkeypatch
):
    monkeypatch.setattr("kist.kicad.discovery.detect_kicad", lambda: object())
    monkeypatch.setattr(
        "kist.kicad.indexer.clone_symbol_to_local_library",
        lambda *args, **kwargs: "00k-ICs:HV100K5-G",
    )
    monkeypatch.setattr(
        "kist.kicad.indexer.linked_footprint_for_symbol",
        lambda *args, **kwargs: "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    )

    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form.query_one("#category", Select).value = "IC"
        form._on_library_search_result(
            ("clone", "Regulator_Current:HV100K5-G"), "symbol"
        )

        assert form.query_one("#symbol", Input).value == "00k-ICs:HV100K5-G"
        assert (
            form.query_one("#footprint", Input).value
            == "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
        )


async def test_clone_symbol_without_category_warns(editable_app, monkeypatch):
    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form.query_one("#category", Select).value = Select.BLANK
        form._on_library_search_result(
            ("clone", "Regulator_Current:HV100K5-G"), "symbol"
        )

        # Symbol field should remain empty -- clone was rejected.
        assert form.query_one("#symbol", Input).value == ""


async def test_clone_footprint_selection_updates_local_ref(editable_app, monkeypatch):
    monkeypatch.setattr("kist.kicad.discovery.detect_kicad", lambda: object())
    monkeypatch.setattr(
        "kist.kicad.indexer.clone_footprint_to_local_library",
        lambda *args, **kwargs: "00k-Resistor_SMD:R_0603_1608Metric",
    )

    async with editable_app.run_test():
        form = editable_app.query_one("#form", PartForm)
        form._on_library_search_result(
            ("clone", "Resistor_SMD:R_0603_1608Metric"), "footprint"
        )

        assert (
            form.query_one("#footprint", Input).value
            == "00k-Resistor_SMD:R_0603_1608Metric"
        )


# -- Inline category creation ---


class InlineCatApp(KistApp):
    """KistApp subclass for testing inline category creation."""

    CSS_PATH = None
    CSS = ""

    def __init__(self, library_path):
        super().__init__()
        self._test_library_path = library_path

    def _discover_library(self):
        self.library_path = self._test_library_path
        self.library_config = load_library_config(self._test_library_path)

    def get_default_screen(self):
        from textual.screen import Screen

        class FormScreen(Screen):
            def compose(self_inner) -> ComposeResult:
                yield PartForm(mode="editable", id="form")

            def on_mount(self_inner):
                config = self.library_config
                if config:
                    self_inner.query_one("#form", PartForm).set_categories(
                        config.categories
                    )

        return FormScreen()


@pytest.fixture(autouse=True)
def _isolate_inline_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


@pytest.fixture
def inline_lib(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    cfg = LibraryConfig(categories={"RES": CategoryDef(name="Resistors", refdes="R")})
    save_library_config(lib, cfg)
    return lib


async def test_set_categories_includes_new_sentinel(inline_lib):
    app = InlineCatApp(inline_lib)
    async with app.run_test():
        form = app.screen.query_one("#form", PartForm)
        cat_select = form.query_one("#category", Select)
        values = [opt[1] for opt in cat_select._options]
        assert _NEW_CATEGORY in values
        assert "RES" in values


async def test_new_sentinel_not_in_readonly():
    """Readonly forms should not show the New... option."""
    app = PartFormApp(mode="readonly")
    async with app.run_test():
        form = app.query_one("#form", PartForm)
        categories = {"IC": CategoryDef(name="ICs", refdes="U")}
        form._mode = "readonly"
        form.set_categories(categories)
        cat_select = form.query_one("#category", Select)
        values = [opt[1] for opt in cat_select._options]
        assert _NEW_CATEGORY not in values
        assert "IC" in values


async def test_new_category_callback_saves_and_selects(inline_lib):
    app = InlineCatApp(inline_lib)
    async with app.run_test():
        form = app.screen.query_one("#form", PartForm)

        # Simulate the callback that CategoryFormModal would invoke
        new_cat = CategoryDef(name="Optocouplers", refdes="U")
        form._on_new_category_result(("OPTO", new_cat))

        # Category should be selected
        cat_select = form.query_one("#category", Select)
        assert cat_select.value == "OPTO"

        # New category should appear in options
        values = [opt[1] for opt in cat_select._options]
        assert "OPTO" in values
        assert "RES" in values  # existing category preserved

        # Config should be persisted
        loaded = load_library_config(inline_lib)
        assert "OPTO" in loaded.categories
        assert loaded.categories["OPTO"].name == "Optocouplers"


async def test_new_category_cancel_leaves_blank(inline_lib):
    app = InlineCatApp(inline_lib)
    async with app.run_test():
        form = app.screen.query_one("#form", PartForm)

        # Simulate cancel (None result)
        form._on_new_category_result(None)

        cat_select = form.query_one("#category", Select)
        assert cat_select.value == Select.BLANK
