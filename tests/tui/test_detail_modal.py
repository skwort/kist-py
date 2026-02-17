"""DetailModal tests -- open, display, edit, delete, and browse integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, Label

from kist.core.config import load_library_config
from kist.core.database import PartsDatabase
from kist.core.library import init_library
from kist.models.part import Mounting, ProprietaryPart, Tier
from kist.tui.app import KistApp
from kist.tui.screens.browse import BrowseScreen
from kist.tui.screens.detail import ConfirmModal, DetailModal
from kist.tui.widgets.part_form import PartForm

pytestmark = pytest.mark.slow


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


class BrowseApp(KistApp):
    """Minimal app for testing browse + detail modal integration."""

    CSS_PATH = None
    CSS = ""

    def __init__(self, library_path: Path | None = None) -> None:
        super().__init__()
        self._test_library_path = library_path

    def get_default_screen(self) -> BrowseScreen:
        return BrowseScreen()

    def _discover_library(self) -> None:
        if self._test_library_path:
            self.library_path = self._test_library_path
            self.library_config = load_library_config(self._test_library_path)


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


async def test_escape_dismisses_without_callback():
    """Dismiss without changes closes the modal (no callback needed)."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()
        await pilot.press("escape")

        assert not isinstance(app.screen, DetailModal)


# -- Edit toggle ---


async def test_e_enters_edit_mode():
    """Pressing 'e' in readonly mode switches to editable."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        form = app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "readonly"

        await pilot.press("e")
        assert form.mode == "editable"


async def test_escape_exits_edit_mode():
    """Pressing escape in edit mode with no changes returns to readonly."""
    part = _make_proprietary_part()
    app = BrowseApp()

    async with app.run_test() as pilot:
        await app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("e")
        form = app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "editable"

        await pilot.press("escape")
        assert form.mode == "readonly"
        # Still on detail modal, not dismissed
        assert isinstance(app.screen, DetailModal)


# -- Edit save ---


def _persisted_part(library_path: Path) -> ProprietaryPart:
    """Load the part from the database so it has an IPN assigned."""
    db = PartsDatabase(library_path / "parts.json")
    db.load()
    parts = db.list_parts()
    assert len(parts) == 1
    return parts[0]  # type: ignore[return-value]


async def test_edit_save_persists_changes(browse_app, library_path):
    """Editing and saving updates the part in the database."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        # Switch to edit mode
        await pilot.press("e")
        form = browse_app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "editable"

        # Change the description
        desc_input = form.query_one("#description", Input)
        desc_input.value = "Updated MCU description"

        # Save
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Should switch back to readonly
        assert form.mode == "readonly"

        # Verify in database
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        parts = db.list_parts()
        assert len(parts) == 1
        assert parts[0].description == "Updated MCU description"


async def test_edit_save_refreshes_readonly_symbol_label(browse_app, library_path):
    """Saving in edit mode updates readonly label values in the open modal."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("e")
        form = browse_app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "editable"

        symbol_input = form.query_one("#symbol", Input)
        symbol_input.value = "MCU_ST:STM32F405_NEW"

        await pilot.press("ctrl+s")
        await pilot.pause()

        assert form.mode == "readonly"
        assert form.query_one("#symbol-ro", Label).content == "MCU_ST:STM32F405_NEW"


async def test_save_ignored_in_readonly_mode(browse_app, library_path):
    """ctrl+s does nothing when not in edit mode."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        form = browse_app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "readonly"

        # Save should be a no-op
        await pilot.press("ctrl+s")
        assert form.mode == "readonly"


# -- Delete ---


async def test_delete_removes_part(browse_app, library_path):
    """Deleting a part removes it from the database and dismisses the modal."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        # Press d to open confirm modal
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(browse_app.screen, ConfirmModal)

        # Click confirm
        await pilot.click("#confirm-ok")
        await pilot.pause()

        # Modal should be dismissed
        assert not isinstance(browse_app.screen, DetailModal)

        # Part removed from database
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        assert len(db.list_parts()) == 0


async def test_delete_cancel_keeps_part(browse_app, library_path):
    """Cancelling the delete confirmation leaves the part intact."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()
        assert isinstance(browse_app.screen, ConfirmModal)

        # Cancel
        await pilot.press("escape")
        await pilot.pause()

        # Back to detail modal, part still exists
        assert isinstance(browse_app.screen, DetailModal)
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        assert len(db.list_parts()) == 1


# -- Unsaved changes prompt ---


async def test_escape_in_edit_mode_with_no_changes_goes_readonly(
    browse_app, library_path
):
    """Escape in edit mode returns to readonly if form is unchanged."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("e")
        form = browse_app.screen.query_one("#detail-form", PartForm)
        assert form.mode == "editable"

        await pilot.press("escape")
        assert form.mode == "readonly"
        assert isinstance(browse_app.screen, DetailModal)


async def test_escape_in_edit_mode_with_changes_prompts(browse_app, library_path):
    """Escape in edit mode shows confirm dialog when form has changes."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("e")
        form = browse_app.screen.query_one("#detail-form", PartForm)
        form.query_one("#description", Input).value = "Changed description"

        # Escape should show confirm dialog
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(browse_app.screen, ConfirmModal)

        # Cancel keeps us in edit mode
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(browse_app.screen, DetailModal)
        assert form.mode == "editable"


async def test_escape_with_changes_confirm_reverts_to_readonly(
    browse_app, library_path
):
    """Confirming discard returns to readonly mode with original data."""
    part = _persisted_part(library_path)

    async with browse_app.run_test() as pilot:
        await browse_app.push_screen(DetailModal(part))
        await pilot.pause()

        await pilot.press("e")
        form = browse_app.screen.query_one("#detail-form", PartForm)
        form.query_one("#description", Input).value = "Changed description"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(browse_app.screen, ConfirmModal)

        # Confirm discard
        await pilot.click("#confirm-ok")
        await pilot.pause()

        # Back to readonly in the detail modal, not dismissed
        assert isinstance(browse_app.screen, DetailModal)
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


async def test_browse_refreshes_after_delete(browse_app, library_path):
    """Browse table refreshes after a part is deleted in the detail modal."""
    async with browse_app.run_test() as pilot:
        table = browse_app.query_one("#parts-table")
        assert table.row_count == 1

        # Open detail modal
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(browse_app.screen, DetailModal)

        # Delete the part
        await pilot.press("d")
        await pilot.pause()
        await pilot.click("#confirm-ok")
        await pilot.pause()

        # Back on browse screen, table hidden and empty state shown
        assert isinstance(browse_app.screen, BrowseScreen)
        assert table.display is False
        assert browse_app.query_one("#empty-state").display is True
