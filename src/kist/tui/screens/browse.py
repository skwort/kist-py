"""Browse screen -- library overview with category sidebar and parts table."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label

from kist import __version__
from kist.tui.widgets.header import KistHeader


class BrowseScreen(Screen):
    """Main screen showing the parts library."""

    TITLE = "Kist"
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("slash", "focus_search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        yield KistHeader(icon="\N{PACKAGE}", page_title="Browse")
        yield Label("Browse screen placeholder", id="placeholder")
        yield Footer()

    def action_focus_search(self) -> None:
        pass
