"""AddScreen tests -- form population, validation, and save flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, Select

from kist.core.config import load_library_config
from kist.core.database import PartsDatabase
from kist.core.library import init_library
from kist.models.part import Mounting, ProprietaryPart, Tier
from kist.providers.models import ProviderProduct
from kist.tui.app import KistApp
from kist.tui.screens.add import AddScreen
from kist.tui.widgets.part_form import PartForm


class AddScreenApp(KistApp):
    """Minimal app for testing AddScreen in isolation."""

    CSS_PATH = None
    CSS = ""

    def __init__(
        self,
        library_path: Path | None = None,
        url_or_mpn: str | None = None,
    ) -> None:
        super().__init__()
        self._test_library_path = library_path
        self._url_or_mpn_arg = url_or_mpn

    def get_default_screen(self) -> AddScreen:
        return AddScreen(url_or_mpn=self._url_or_mpn_arg)

    def _discover_library(self) -> None:
        if self._test_library_path:
            self.library_path = self._test_library_path
            self.library_config = load_library_config(self._test_library_path)


@pytest.fixture
def app():
    return AddScreenApp()


@pytest.fixture
def library_path(tmp_path):
    """Create a temporary kist library and return its path."""
    return init_library(tmp_path / "lib")


@pytest.fixture
def app_with_library(library_path):
    return AddScreenApp(library_path=library_path)


# -- Screen mount ---


async def test_add_screen_has_part_form(app):
    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        assert form is not None
        assert form.mode == "editable"


async def test_add_screen_has_url_input(app):
    async with app.run_test():
        url_input = app.query_one("#url-input", Input)
        assert url_input is not None


async def test_url_input_populated_from_arg():
    """CLI argument pre-fills the URL input."""
    test_app = AddScreenApp(url_or_mpn="STM32F405RGT6")
    async with test_app.run_test():
        url_input = test_app.query_one("#url-input", Input)
        assert url_input.value == "STM32F405RGT6"


# -- Provider population ---


def _make_ic_product() -> ProviderProduct:
    return ProviderProduct(
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        description="ARM Cortex-M4 MCU",
        detailed_description="ARM Cortex-M4 MCU, 1MB Flash",
        supplier_name="DigiKey",
        supplier_sku="497-STM32F405RGT6-ND",
        supplier_url="https://www.digikey.com/en/products/detail/stm/STM32F405RGT6/123",
        datasheet_url="https://www.st.com/resource/en/datasheet/stm32f405rg.pdf",
        category="IC",
        package="LQFP-64",
        mounting="smd",
        parameters={"frequency": "168MHz", "flash": "1MB"},
    )


def _make_resistor_product() -> ProviderProduct:
    return ProviderProduct(
        mpn="RC0603FR-0710KL",
        manufacturer="Yageo",
        description="10 kOhms 1% 0.1W Chip Resistor",
        detailed_description="",
        supplier_name="DigiKey",
        supplier_sku="311-10.0KHRCT-ND",
        category="RES",
        parameters={"resistance": "10 kOhms", "tolerance": "1%"},
    )


def _make_diode_product() -> ProviderProduct:
    return ProviderProduct(
        mpn="1N4148W-7-F",
        manufacturer="Diodes Incorporated",
        description="Diode Standard 100V 300mA",
        detailed_description="",
        supplier_name="DigiKey",
        supplier_sku="1N4148W-FDICT-ND",
        category="DIO",
        parameters={},
    )


async def test_load_from_provider_populates_form(app):
    product = _make_ic_product()

    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.load_from_provider(product)

        assert form.query_one("#mpn", Input).value == "STM32F405RGT6"
        assert form.query_one("#manufacturer", Input).value == "STMicroelectronics"
        assert form.query_one("#description", Input).value == "ARM Cortex-M4 MCU"
        assert form.query_one("#package", Input).value == "LQFP-64"
        assert form.query_one("#mounting", Select).value == Mounting.SMD
        assert form.query_one("#tier", Select).value == Tier.PROPRIETARY
        assert form.query_one("#category", Select).value == "IC"
        assert form.query_one("#datasheet", Input).value == (
            "https://www.st.com/resource/en/datasheet/stm32f405rg.pdf"
        )


async def test_load_from_provider_adds_supplier(app):
    product = _make_ic_product()

    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.load_from_provider(product)

        d = form.to_dict()
        assert product.supplier_name in d["suppliers"]
        assert d["suppliers"]["DigiKey"]["sku"] == "497-STM32F405RGT6-ND"


async def test_load_from_provider_adds_specs(app):
    product = _make_ic_product()

    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.load_from_provider(product)

        d = form.to_dict()
        assert d["specifications"]["frequency"] == "168MHz"
        assert d["specifications"]["flash"] == "1MB"


async def test_load_from_provider_detects_jellybean_tier(app):
    product = _make_resistor_product()

    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.load_from_provider(product)

        assert form.query_one("#tier", Select).value == Tier.JELLYBEAN


async def test_load_from_provider_detects_semi_jellybean_tier(app):
    product = _make_diode_product()

    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.load_from_provider(product)

        assert form.query_one("#tier", Select).value == Tier.SEMI_JELLYBEAN


# -- Clear ---


async def test_clear_resets_form(app):
    async with app.run_test():
        form = app.query_one("#part-form", PartForm)

        # Populate some fields
        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#mpn", Input).value = "TEST123"
        form.query_one("#manufacturer", Input).value = "TestCorp"
        form.query_one("#package", Input).value = "SO8"
        form._add_spec_to_table("resistance", "10k")

        form.clear()

        assert form.query_one("#tier", Select).value == Select.BLANK
        assert form.query_one("#mpn", Input).value == ""
        assert form.query_one("#manufacturer", Input).value == ""
        assert form.query_one("#package", Input).value == ""
        d = form.to_dict()
        assert d["specifications"] is None


# -- Save validation ---


async def test_save_requires_tier(app):
    async with app.run_test():
        # Form is empty -- save should fail on missing tier
        app.screen.action_save()

        form = app.query_one("#part-form", PartForm)
        # Form should NOT be cleared (no successful save)
        assert form.query_one("#tier", Select).value == Select.BLANK


async def test_save_requires_category(app):
    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.query_one("#tier", Select).value = Tier.PROPRIETARY

        app.screen.action_save()

        # Category still blank -- save didn't succeed
        assert form.query_one("#category", Select).value == Select.BLANK


async def test_save_requires_library(app):
    """Save fails gracefully when no library is discovered."""
    async with app.run_test():
        form = app.query_one("#part-form", PartForm)
        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#category", Select).value = "IC"
        form.query_one("#mpn", Input).value = "TEST"
        form.query_one("#manufacturer", Input).value = "Corp"

        app.screen.action_save()

        # Form not cleared -- save failed because no library
        assert form.query_one("#mpn", Input).value == "TEST"


async def test_save_requires_mpn_for_proprietary(app_with_library):
    async with app_with_library.run_test():
        form = app_with_library.query_one("#part-form", PartForm)
        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#category", Select).value = "IC"
        # MPN left empty

        app_with_library.screen.action_save()

        # Form not cleared -- save failed
        assert form.query_one("#tier", Select).value == Tier.PROPRIETARY


# -- Save flow ---


async def test_save_proprietary_part(app_with_library, library_path):
    async with app_with_library.run_test():
        form = app_with_library.query_one("#part-form", PartForm)

        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#category", Select).value = "IC"
        form.query_one("#mpn", Input).value = "STM32F405RGT6"
        form.query_one("#manufacturer", Input).value = "STMicroelectronics"
        form.query_one("#package", Input).value = "LQFP-64"

        app_with_library.screen.action_save()

        # Part saved to database
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        parts = db.list_parts()
        assert len(parts) == 1
        part = parts[0]
        assert isinstance(part, ProprietaryPart)
        assert part.mpn == "STM32F405RGT6"
        assert "IC" in part.name
        assert "STM32F405RGT6" in part.name

        # Form cleared after successful save
        assert form.query_one("#tier", Select).value == Select.BLANK
        assert form.query_one("#mpn", Input).value == ""


async def test_save_jellybean_part(app_with_library, library_path):
    async with app_with_library.run_test():
        form = app_with_library.query_one("#part-form", PartForm)

        form.query_one("#tier", Select).value = Tier.JELLYBEAN
        form.query_one("#category", Select).value = "RES"
        form.query_one("#package", Input).value = "0603"
        form.query_one("#mounting", Select).value = Mounting.SMD
        form._add_spec_to_table("resistance", "10k")
        form._add_spec_to_table("tolerance", "1%")

        app_with_library.screen.action_save()

        db = PartsDatabase(library_path / "parts.json")
        db.load()
        parts = db.list_parts()
        assert len(parts) == 1
        assert parts[0].tier == Tier.JELLYBEAN
        assert "RES" in parts[0].name
        assert parts[0].reference == "R"

        # Form cleared
        assert form.query_one("#tier", Select).value == Select.BLANK


async def test_save_duplicate_shows_error(app_with_library, library_path):
    """Saving the same part twice shows a duplicate error."""
    async with app_with_library.run_test():
        form = app_with_library.query_one("#part-form", PartForm)

        # Save first part
        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#category", Select).value = "IC"
        form.query_one("#mpn", Input).value = "LM358"
        form.query_one("#manufacturer", Input).value = "TI"
        app_with_library.screen.action_save()

        # Form should be cleared after first save
        assert form.query_one("#mpn", Input).value == ""

        # Try to save same part again
        form.query_one("#tier", Select).value = Tier.PROPRIETARY
        form.query_one("#category", Select).value = "IC"
        form.query_one("#mpn", Input).value = "LM358"
        form.query_one("#manufacturer", Input).value = "TI"
        app_with_library.screen.action_save()

        # Form NOT cleared -- duplicate error
        assert form.query_one("#mpn", Input).value == "LM358"

        # Only one part in database
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        assert len(db.list_parts()) == 1
