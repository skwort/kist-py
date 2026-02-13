"""Kist TUI application."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.app import App, SystemCommand
from textual.content import Content
from textual.reactive import reactive
from textual.screen import Screen

from kist.core.library import find_library
from kist.errors import LibraryNotFoundError
from kist.tui.themes import KIST_DARK


class KistApp(App):
    """Terminal interface for managing a kist parts library."""

    CSS_PATH = "kist.tcss"
    ENABLE_COMMAND_PALETTE = True

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    library_path: reactive[Path | None] = reactive(None)

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
        self.register_theme(KIST_DARK)
        self.theme = "kist-dark"
        self._discover_library()
        if self._start_screen == "add":
            from kist.tui.screens.add import AddScreen

            self.push_screen(AddScreen(url_or_mpn=self._url_or_mpn))

    def _discover_library(self) -> None:
        try:
            self.library_path = find_library()
        except LibraryNotFoundError:
            self.library_path = None

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

    def _push_add_screen(self) -> None:
        from kist.tui.screens.add import AddScreen

        self.push_screen(AddScreen())


def run_tui(
    start_screen: str | None = None,
    url_or_mpn: str | None = None,
) -> None:
    """Entry point for launching the TUI from the CLI."""
    app = KistApp(start_screen=start_screen, url_or_mpn=url_or_mpn)
    app.run()
