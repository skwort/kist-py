"""LibrarySearchModal tests -- search, filter, select, and cancel."""

import asyncio

from textual.app import App
from textual.widgets import DataTable, Input, Label

from kist.kicad.indexer import LibraryItem
from kist.tui.modals.library_search import LibrarySearchModal

SAMPLE_ITEMS = [
    LibraryItem(library="Resistor_SMD", name="R_0402_1005Metric", source="kicad"),
    LibraryItem(library="Resistor_SMD", name="R_0603_1608Metric", source="kicad"),
    LibraryItem(library="Resistor_SMD", name="R_0805_2012Metric", source="kicad"),
    LibraryItem(library="Capacitor_SMD", name="C_0402_1005Metric", source="kicad"),
    LibraryItem(library="Capacitor_SMD", name="C_0603_1608Metric", source="kicad"),
    LibraryItem(library="QFP", name="LQFP-48_7x7mm_P0.5mm", source="kicad"),
]


class ModalApp(App):
    """Minimal app for testing modals."""

    CSS = ""


async def test_modal_shows_all_items():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        table = app.screen.query_one("#libsearch-table", DataTable)
        assert table.row_count == 6


async def test_modal_shows_status_text():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        status = app.screen.query_one("#libsearch-status", Label)
        assert "6 footprints" in str(status.content)


async def _wait_debounce(pilot) -> None:
    """Wait long enough for the search debounce timer to fire."""
    await asyncio.sleep(0.25)
    await pilot.pause()


async def test_modal_filters_by_search():
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        search = app.screen.query_one("#libsearch-input", Input)
        search.value = "0603"
        await _wait_debounce(pilot)
        table = app.screen.query_one("#libsearch-table", DataTable)
        assert table.row_count == 2  # R_0603 and C_0603


async def test_modal_filter_updates_status():
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        search = app.screen.query_one("#libsearch-input", Input)
        search.value = "QFP"
        await _wait_debounce(pilot)
        status = app.screen.query_one("#libsearch-status", Label)
        assert "1 / 6" in str(status.content)


async def test_modal_filter_case_insensitive():
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        search = app.screen.query_one("#libsearch-input", Input)
        search.value = "capacitor"
        await _wait_debounce(pilot)
        table = app.screen.query_one("#libsearch-table", DataTable)
        assert table.row_count == 2


async def test_modal_escape_dismisses():
    app = ModalApp()
    async with app.run_test() as pilot:
        results = []
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS), callback=results.append)
        assert isinstance(app.screen, LibrarySearchModal)
        await pilot.press("escape")
        assert not isinstance(app.screen, LibrarySearchModal)
        assert results == [None]


async def test_modal_row_select_returns_reference():
    app = ModalApp()
    async with app.run_test() as pilot:
        results = []
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS), callback=results.append)
        table = app.screen.query_one("#libsearch-table", DataTable)
        # Move to first row and select it
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        assert len(results) == 1
        assert results[0] == "Resistor_SMD:R_0402_1005Metric"


async def test_modal_empty_items():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibrarySearchModal([], title="Symbols"))
        table = app.screen.query_one("#libsearch-table", DataTable)
        assert table.row_count == 0
        status = app.screen.query_one("#libsearch-status", Label)
        assert "0 symbols" in str(status.content)


async def test_modal_clear_search_restores_all():
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Footprints"))
        search = app.screen.query_one("#libsearch-input", Input)
        search.value = "QFP"
        await _wait_debounce(pilot)
        table = app.screen.query_one("#libsearch-table", DataTable)
        assert table.row_count == 1
        # Clear search
        search.value = ""
        await _wait_debounce(pilot)
        assert table.row_count == 6


async def test_modal_border_title():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibrarySearchModal(SAMPLE_ITEMS, title="Symbols"))
        container = app.screen.query_one("#libsearch-container")
        assert container.border_title == "Symbols"
