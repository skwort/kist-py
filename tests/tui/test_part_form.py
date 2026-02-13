"""PartForm widget tests -- mode switching, tier visibility, data flow."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Label, Select

from kist.models.part import (
    Mounting,
    ProprietaryPart,
    SupplierInfo,
    Tier,
)
from kist.tui.widgets.part_form import PartForm


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
        name="IC-STM32F405RGT6-LQFP64",
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
