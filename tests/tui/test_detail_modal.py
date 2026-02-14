"""DetailModal tests -- open, display, edit, delete, and browse integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.reactive import reactive
from textual.widgets import Label

from kist.core.database import PartsDatabase
from kist.core.library import init_library
from kist.models.part import Mounting, ProprietaryPart, Tier
from kist.tui.screens.browse import BrowseScreen
from kist.tui.screens.detail import DetailModal
from kist.tui.widgets.part_form import PartForm


def _make_proprietary_part() -> ProprietaryPart:
    return ProprietaryPart(
        name="IC-STM32F405RGT6-LQFP64",
        tier=Tier.PROPRIETARY,
        description="ARM Cortex-M4 MCU",
        category="IC",
        package="LQFP-64",
        mounting=Mounting.SMD,
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        symbol="MCU_ST:STM32F405RGTx",
        footprint="Package_QFP:LQFP-64",
        value="STM32F405RGT6",
        reference="U",
        tags=["arm", "cortex-m4"],
    )


class BrowseApp(App):
    """Minimal app for testing browse + detail modal integration."""

    CSS = ""
    library_path: reactive[Path | None] = reactive(None)

    def __init__(self, library_path: Path | None = None) -> None:
        super().__init__()
        self._library_path = library_path

    def get_default_screen(self) -> BrowseScreen:
        return BrowseScreen()

    def on_mount(self) -> None:
        self.library_path = self._library_path


@pytest.fixture
def library_path(tmp_path):
    """Create a temporary kist library with one part."""
    lib = init_library(tmp_path / "lib")
    db = PartsDatabase(lib / "parts.json")
    db.load()
    part = _make_proprietary_part()
    db.add(part)
    return lib


@pytest.fixture
def browse_app(library_path):
    return BrowseApp(library_path=library_path)


# -- Modal open/close ---


async def test_detail_modal_opens_with_part_data():
    """DetailModal shows part data in a readonly PartForm."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        form = app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "readonly"
        assert form.query_one("#mpn-ro", Label).content == "STM32F405RGT6"
        assert form.query_one("#manufacturer-ro", Label).content == "STMicroelectronics"


async def test_detail_modal_border_title():
    """Modal container shows part name in border title."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        container = app.screen.query_one("#detail-container")
        assert container.border_title == "IC-STM32F405RGT6-LQFP64"


async def test_escape_dismisses_modal():
    """Escape closes the detail modal."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)
        await pilot.press("escape")
        assert not isinstance(app.screen, DetailModal)


async def test_escape_returns_false_when_unchanged():
    """Dismiss without changes returns False."""
    part = _make_proprietary_part()
    result = None

    def on_dismiss(value: bool | None) -> None:
        nonlocal result
        result = value

    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part), callback=on_dismiss)
        await pilot.pause()
        await pilot.press("escape")

        assert result is False


# -- Edit toggle ---


async def test_edit_toggle():
    """Pressing 'e' toggles between readonly and editable mode."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        form = app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "readonly"

        await pilot.press("e")
        assert form.mode == "editable"

        await pilot.press("e")
        assert form.mode == "readonly"


# -- Browse integration ---


async def test_browse_row_select_opens_detail(browse_app):
    """Selecting a row in the browse table opens the detail modal."""
    async with browse_app.run_test() as pilot:
        # Table should have one row from the fixture
        table = browse_app.query_one("#parts-table")
        assert table.row_count == 1

        # Focus and select
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(browse_app.screen, DetailModal)
        form = browse_app.screen.query_one("#detail-form", PartForm)
        assert form.query_one("#mpn-ro", Label).content == "STM32F405RGT6"
