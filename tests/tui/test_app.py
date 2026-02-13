"""TUI app shell tests -- Phase 1 smoke tests."""

import pytest

from kist.tui.app import KistApp
from kist.tui.screens.add import AddScreen
from kist.tui.screens.browse import BrowseScreen


@pytest.fixture
def app():
    return KistApp()


async def test_default_screen_is_browse(app):
    async with app.run_test():
        assert isinstance(app.screen, BrowseScreen)


async def test_header_shows_title(app):
    async with app.run_test():
        header_title = app.query_one("HeaderTitle")
        content = header_title.render()
        assert "Kist" in str(content)


async def test_add_screen_pushed_on_start():
    app = KistApp(start_screen="add")
    async with app.run_test():
        assert isinstance(app.screen, AddScreen)


async def test_add_screen_has_part_form():
    app = KistApp(start_screen="add", url_or_mpn="https://example.com")
    async with app.run_test():
        form = app.screen.query_one("#part-form")
        assert form is not None


async def test_escape_pops_add_screen():
    app = KistApp(start_screen="add")
    async with app.run_test() as pilot:
        assert isinstance(app.screen, AddScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, BrowseScreen)


async def test_quit_from_browse(app):
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app._exit


async def test_kist_dark_theme_registered(app):
    async with app.run_test():
        assert "kist-dark" in app.available_themes


async def test_library_path_none_outside_library(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async with app.run_test():
        assert app.library_path is None


async def test_add_part_in_system_commands(app):
    async with app.run_test():
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Add part" in titles
