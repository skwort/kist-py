"""Kist TUI application."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.app import App, SystemCommand
from textual.content import Content
from textual.reactive import reactive
from textual.screen import Screen

from kist.core.check import check_library
from kist.core.config import load_global_config
from kist.core.config import load_library_config as _load_library_config
from kist.core.config import save_library_config as _save_library_config
from kist.core.database import PartsDatabase
from kist.core.library import find_library
from kist.core.sync import sync_symbols
from kist.errors import LibraryNotFoundError
from kist.models.config import LibraryConfig
from kist.models.part import Ipn, Part
from kist.tui.themes import NULL_THEME


class KistApp(App):
    """Terminal interface for managing a kist parts library."""

    CSS_PATH = "kist.tcss"
    ENABLE_COMMAND_PALETTE = True

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    library_path: reactive[Path | None] = reactive(None)
    library_config: reactive[LibraryConfig | None] = reactive(None)
    parts_version: reactive[int] = reactive(0)

    def __init__(
        self,
        start_screen: str | None = None,
        url_or_mpn: str | None = None,
    ) -> None:
        super().__init__()
        self._start_screen = start_screen
        self._url_or_mpn = url_or_mpn

    def get_default_screen(self) -> Screen:
        from kist.tui.screens.browse import BrowseScreen

        return BrowseScreen()

    def on_mount(self) -> None:
        self.register_theme(NULL_THEME)
        # Apply saved theme from global config
        global_cfg = load_global_config()
        if global_cfg.theme in self.available_themes:
            self.theme = global_cfg.theme
        else:
            self.theme = "null"
        self._discover_library()
        if self._start_screen == "add":
            from kist.tui.screens.add import AddScreen

            self.push_screen(AddScreen(url_or_mpn=self._url_or_mpn))

    def _discover_library(self) -> None:
        try:
            result = find_library()
            self.library_path = result.library_root
            self.library_config = _load_library_config(result.library_root)
        except LibraryNotFoundError:
            self.library_path = None
            self.library_config = None

    # -- Mutation methods ---

    def save_part(self, part: Part, replacing: Ipn | None = None) -> None:
        """Persist a part and run the post-mutation pipeline."""
        assert self.library_path is not None
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        if replacing:
            db.remove(replacing)
        db.add(part)
        self._after_mutation(db)

    def delete_part(self, ipn: Ipn) -> None:
        """Remove a part and run the post-mutation pipeline."""
        assert self.library_path is not None
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        db.remove(ipn)
        self._after_mutation(db)

    def update_library_config(self, config: LibraryConfig) -> None:
        """Save library config to disk and update the reactive attribute."""
        assert self.library_path is not None
        _save_library_config(self.library_path, config)
        self.library_config = config

    def _after_mutation(self, db: PartsDatabase) -> None:
        """Post-mutation side effects: sync, UI refresh."""
        assert self.library_path is not None
        if self.library_config:
            sync_symbols(self.library_path, db, self.library_config)
        self.parts_version += 1

    def format_title(self, title: str, sub_title: str) -> Content:
        """
        Format title with ` -- ` separator instead of unicode em-dash.
        """
        if sub_title:
            return Content.assemble(
                title,
                (" -- ", "dim"),
                (sub_title, "dim"),
            )
        return Content(title)

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Add part",
            "Add a new part to the library",
            self._push_add_screen,
        )
        yield SystemCommand(
            "Settings",
            "Open settings",
            self._push_settings,
        )
        if self.library_path:
            yield SystemCommand(
                "Sync to KiCad",
                "Push parts database to .kicad_sym files",
                self._run_sync,
            )
            yield SystemCommand(
                "Check library",
                "Validate part names and check for duplicates",
                self._run_check,
            )
            yield SystemCommand(
                "Manage categories",
                "Add, edit, or delete category definitions",
                self._push_category_manager,
            )

    # -- Command handlers ---

    def _push_add_screen(self) -> None:
        from kist.tui.screens.add import AddScreen

        self.push_screen(AddScreen())

    def _push_settings(self) -> None:
        from kist.tui.modals.settings import SettingsModal

        self.push_screen(SettingsModal(self.library_path))

    def _push_category_manager(self) -> None:
        from kist.tui.modals.categories import CategoryManagerModal

        if self.library_path:
            self.push_screen(CategoryManagerModal(self.library_path))

    def _run_check(self) -> None:
        from kist.tui.modals.check import LibraryCheckModal

        if not self.library_path or not self.library_config:
            return
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        issues = check_library(db, self.library_config)
        self.push_screen(LibraryCheckModal(issues))

    def _run_sync(self) -> None:
        if not self.library_path or not self.library_config:
            return
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        sync_symbols(self.library_path, db, self.library_config)
        count = len(db.list_parts())
        self.notify(f"Synced {count} part{'s' if count != 1 else ''} to KiCad")


def run_tui(
    start_screen: str | None = None,
    url_or_mpn: str | None = None,
) -> None:
    """Entry point for launching the TUI from the CLI."""
    app = KistApp(start_screen=start_screen, url_or_mpn=url_or_mpn)
    app.run()
