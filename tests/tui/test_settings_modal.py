"""SettingsModal tests -- theme persistence, library fields."""

import pytest
from textual.app import App
from textual.widgets import Input, Select

from kist.core.config import (
    load_global_config,
    load_library_config,
    save_library_config,
)
from kist.models.config import LibraryConfig
from kist.tui.modals.settings import SettingsModal
from kist.tui.themes import KIST_DARK


class SettingsApp(App):
    CSS = ""

    def on_mount(self) -> None:
        self.register_theme(KIST_DARK)
        self.theme = "kist-dark"


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


@pytest.fixture
def library_path(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    save_library_config(lib, LibraryConfig(library_prefix="00k", suppliers=["digikey"]))
    return lib


async def test_theme_change_persists(library_path):
    app = SettingsApp()
    async with app.run_test() as pilot:
        await app.push_screen(SettingsModal(library_path))
        app.screen.query_one("#setting-theme", Select).value = "nord"
        await pilot.pause()
        # Live preview applied
        assert app.theme == "nord"
        await pilot.press("ctrl+s")
        await pilot.pause()
        cfg = load_global_config()
        assert cfg.theme == "nord"


async def test_cancel_reverts_theme():
    app = SettingsApp()
    async with app.run_test() as pilot:
        await app.push_screen(SettingsModal())
        app.screen.query_one("#setting-theme", Select).value = "dracula"
        await pilot.pause()
        assert app.theme == "dracula"
        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == "kist-dark"


async def test_library_fields_save(library_path):
    app = SettingsApp()
    async with app.run_test() as pilot:
        await app.push_screen(SettingsModal(library_path))
        app.screen.query_one("#setting-prefix", Input).value = "xyz"
        app.screen.query_one("#setting-suppliers", Input).value = "mouser, lcsc"
        await pilot.press("ctrl+s")
        await pilot.pause()
        cfg = load_library_config(library_path)
        assert cfg.library_prefix == "xyz"
        assert cfg.suppliers == ["mouser", "lcsc"]


async def test_no_library_hides_library_sections():
    app = SettingsApp()
    async with app.run_test():
        await app.push_screen(SettingsModal(library_path=None))
        results = app.screen.query("#section-library")
        assert len(results) == 0
        results = app.screen.query("#section-directories")
        assert len(results) == 0
