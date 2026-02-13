"""Add screen -- add a new part to the library."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label

from kist import __version__
from kist.tui.widgets.header import KistHeader


class AddScreen(Screen):
    """Full-screen form for adding a new part."""

    TITLE = "Kist"
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        url_or_mpn: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._url_or_mpn = url_or_mpn

    def compose(self) -> ComposeResult:
        yield KistHeader(icon="\N{PACKAGE}", page_title="Add Part")
        text = f"Add part: {self._url_or_mpn}" if self._url_or_mpn else "Add part"
        yield Label(text, id="placeholder")
        yield Footer()

    def action_save(self) -> None:
        self.notify("Save not yet implemented.", severity="warning")

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
