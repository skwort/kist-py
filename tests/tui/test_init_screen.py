"""InitScreen tests -- defaults, category CRUD, library creation."""

from pathlib import Path

import pytest
from textual.widgets import DataTable, Input

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.config import load_library_config
from kist.tui.app import KistApp
from kist.tui.screens.browse import BrowseScreen
from kist.tui.screens.init import InitScreen


class InitApp(KistApp):
    """Minimal app for testing InitScreen in isolation."""

    CSS_PATH = None
    CSS = ""

    def __init__(self, init_path: Path | None = None):
        super().__init__(start_screen="init", init_path=init_path)

    def _discover_library(self) -> None:
        # No library during init
        self.library_path = None
        self.library_config = None


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


# -- Default values ---


async def test_defaults_populated_from_config():
    """Fields are pre-populated from resolve_init_config defaults."""
    app = InitApp()
    async with app.run_test():
        assert app.screen.query_one("#init-prefix", Input).value == "00k"
        assert app.screen.query_one("#init-separator", Input).value == "-"
        assert "digikey" in app.screen.query_one("#init-suppliers", Input).value
        assert app.screen.query_one("#init-symbols-dir", Input).value == "symbols"
        assert app.screen.query_one("#init-footprints-dir", Input).value == "footprints"
        assert app.screen.query_one("#init-models-dir", Input).value == "3dmodels"
        assert app.screen.query_one("#init-blocks-dir", Input).value == "blocks"


async def test_init_path_default_is_cwd():
    """Path field defaults to cwd when no init_path given."""
    app = InitApp()
    async with app.run_test():
        path_value = app.screen.query_one("#init-path", Input).value
        assert path_value == str(Path.cwd())


async def test_init_path_custom(tmp_path):
    """Custom init_path is reflected in the path field."""
    target = tmp_path / "mylib"
    app = InitApp(init_path=target)
    async with app.run_test():
        assert app.screen.query_one("#init-path", Input).value == str(target)


# -- Categories ---


async def test_well_known_categories_seeded():
    """Category table is pre-populated with WELL_KNOWN_CATEGORIES."""
    app = InitApp()
    async with app.run_test():
        table = app.screen.query_one("#init-cat-table", DataTable)
        assert table.row_count == len(WELL_KNOWN_CATEGORIES)


async def test_category_delete():
    """Pressing d on a focused category table row removes the category."""
    app = InitApp()
    async with app.run_test() as pilot:
        table = app.screen.query_one("#init-cat-table", DataTable)
        table.focus()
        await pilot.pause()
        initial_count = table.row_count
        await pilot.press("d")
        await pilot.pause()
        assert table.row_count == initial_count - 1


async def test_category_add():
    """Adding a category via CategoryFormModal updates the table."""
    app = InitApp()
    async with app.run_test() as pilot:
        table = app.screen.query_one("#init-cat-table", DataTable)
        table.focus()
        await pilot.pause()
        initial_count = table.row_count
        await pilot.press("a")
        await pilot.pause()
        # Fill the category form
        app.screen.query_one("#cat-code", Input).value = "OPTO"
        app.screen.query_one("#cat-name", Input).value = "Optocouplers"
        app.screen.query_one("#cat-refdes", Input).value = "U"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert table.row_count == initial_count + 1


async def test_category_edit():
    """Editing a category via CategoryFormModal updates local state."""
    app = InitApp()
    async with app.run_test() as pilot:
        table = app.screen.query_one("#init-cat-table", DataTable)
        table.focus()
        await pilot.pause()
        # Edit the first category (cursor starts at row 0)
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#cat-name", Input).value = "Updated Name"
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Verify the name column was updated
        first_row = table.get_row_at(0)
        assert first_row[1] == "Updated Name"


async def test_category_add_via_button_when_empty():
    """Add button works even when all categories have been deleted."""
    app = InitApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, InitScreen)
        # Delete all categories
        screen._categories.clear()
        screen._reload_categories()
        await pilot.pause()
        table = screen.query_one("#init-cat-table", DataTable)
        assert table.row_count == 0
        # Click Add button
        await pilot.click("#init-cat-add")
        await pilot.pause()
        # Fill the category form
        app.screen.query_one("#cat-code", Input).value = "NEW"
        app.screen.query_one("#cat-name", Input).value = "New Category"
        app.screen.query_one("#cat-refdes", Input).value = "X"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert table.row_count == 1


# -- Library creation ---


async def test_create_library(tmp_path):
    """Create writes config and transitions back to BrowseScreen."""
    target = tmp_path / "newlib"
    app = InitApp(init_path=target)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Library created on disk
        assert (target / ".kist" / "config.toml").exists()
        config = load_library_config(target)
        assert config.library_prefix == "00k"
        assert len(config.categories) == len(WELL_KNOWN_CATEGORIES)
        # App state updated
        assert app.library_path == target.resolve()
        assert app.library_config is not None
        # Popped back to BrowseScreen
        assert isinstance(app.screen, BrowseScreen)


async def test_create_custom_values(tmp_path):
    """Custom prefix/separator/suppliers are persisted to config."""
    target = tmp_path / "custom"
    app = InitApp(init_path=target)
    async with app.run_test() as pilot:
        app.screen.query_one("#init-prefix", Input).value = "xyz"
        app.screen.query_one("#init-separator", Input).value = "_"
        app.screen.query_one("#init-suppliers", Input).value = "mouser, lcsc"
        app.screen.query_one("#init-symbols-dir", Input).value = "sym"
        await pilot.press("ctrl+s")
        await pilot.pause()
        config = load_library_config(target)
        assert config.library_prefix == "xyz"
        assert config.separator == "_"
        assert config.suppliers == ["mouser", "lcsc"]
        assert config.symbols_dir == "sym"


async def test_create_existing_library_shows_error(tmp_path):
    """Creating on an existing library shows error, stays on InitScreen."""
    from kist.core.library import init_library

    target = tmp_path / "existing"
    init_library(target)

    app = InitApp(init_path=target)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Still on InitScreen -- error shown
        assert isinstance(app.screen, InitScreen)


# -- Cancel ---


async def test_cancel_pops_to_browse():
    """Cancel pops back to BrowseScreen."""
    app = InitApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, InitScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, BrowseScreen)
