"""Detail modal -- view, edit, and delete a part from the browse screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer

from kist.models.part import Part
from kist.tui.widgets.part_form import PartForm


class DetailModal(ModalScreen[bool]):
    """
    Modal showing full part details in PartForm readonly mode.

    Returns True on dismiss if the underlying data changed (edit/delete),
    so the browse screen knows to refresh.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("e", "toggle_edit", "Edit"),
    ]

    def __init__(self, part: Part) -> None:
        super().__init__()
        self._part = part
        self._changed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield PartForm(mode="readonly", id="detail-form")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#detail-container").border_title = self._part.name
        self.call_after_refresh(self._load_part)

    def _load_part(self) -> None:
        self.query_one("#detail-form", PartForm).load_part(self._part)

    def action_toggle_edit(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        form.mode = "editable" if form.mode == "readonly" else "readonly"

    def action_close(self) -> None:
        self.dismiss(self._changed)
