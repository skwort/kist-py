"""SettingsModal tests -- theme persistence, library fields."""

import pytest
from textual.widgets import Input, Select

from kist.core.config import (
    load_global_config,
    load_library_config,
    save_library_config,
)
from kist.models.config import LibraryConfig
from kist.tui.app import KistApp
from kist.tui.modals.settings import SettingsModal


class SettingsApp(KistApp):
    CSS_PATH = None
    CSS = ""

    def __init__(self, library_path=None):
        super().__init__()
        self._test_library_path = library_path

    def _discover_library(self):
        if self._test_library_path:
            self.library_path = self._test_library_path
            self.library_config = load_library_config(self._test_library_path)


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
    app = SettingsApp(library_path)
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
        assert app.theme == "null"


async def test_library_fields_save(library_path):
    app = SettingsApp(library_path)
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


async def test_digikey_credentials_save():
    app = SettingsApp()
    async with app.run_test() as pilot:
        await app.push_screen(SettingsModal())
        app.screen.query_one("#setting-dk-client-id", Input).value = "my-id"
        app.screen.query_one("#setting-dk-client-secret", Input).value = "my-secret"
        await pilot.press("ctrl+s")
        await pilot.pause()
        cfg = load_global_config()
        assert cfg.providers.digikey.client_id == "my-id"
        assert cfg.providers.digikey.client_secret == "my-secret"


async def test_digikey_credentials_load():
    from kist.core.config import save_global_config
    from kist.models.config import GlobalConfig

    cfg = GlobalConfig()
    cfg.providers.digikey.client_id = "saved-id"
    cfg.providers.digikey.client_secret = "saved-secret"
    save_global_config(cfg)

    app = SettingsApp()
    async with app.run_test():
        await app.push_screen(SettingsModal())
        assert app.screen.query_one("#setting-dk-client-id", Input).value == "saved-id"
        assert (
            app.screen.query_one("#setting-dk-client-secret", Input).value
            == "saved-secret"
        )


async def test_digikey_credentials_password_mode():
    app = SettingsApp()
    async with app.run_test():
        await app.push_screen(SettingsModal())
        assert app.screen.query_one("#setting-dk-client-id", Input).password is True
        assert app.screen.query_one("#setting-dk-client-secret", Input).password is True
