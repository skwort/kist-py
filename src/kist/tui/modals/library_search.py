"""Library search modal -- fzf-style search for footprints and symbols."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Input, Label

from kist.kicad.indexer import LibraryItem

_MAX_ROWS = 200
_DEBOUNCE_S = 0.15


class LibrarySearchModal(ModalScreen[str | None]):
    """
    Search and select a library item (footprint or symbol).

    Presents an input at the top with filtered results below.
    Substring matching on the full ``Library:Name`` reference.
    Dismisses with the selected reference string, or ``None`` on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, items: list[LibraryItem], title: str = "Footprints") -> None:
        super().__init__()
        self._items = items
        self._title = title
        self._filtered: list[LibraryItem] = list(items)
        self._debounce_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="libsearch-container") as container:
            container.border_title = self._title
            yield Input(placeholder="Type to search...", id="libsearch-input")
            yield Label(self._status_text(), id="libsearch-status")
            yield DataTable(id="libsearch-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#libsearch-table", DataTable)
        table.add_columns("Library", "Name")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._populate_table()
        self.query_one("#libsearch-input", Input).focus()

    def _status_text(self) -> str:
        total = len(self._items)
        matched = len(self._filtered)
        label = self._title.lower()
        if matched == total:
            return f"{total} {label}"
        suffix = f" (showing {_MAX_ROWS})" if matched > _MAX_ROWS else ""
        return f"{matched} / {total} {label}{suffix}"

    def _populate_table(self) -> None:
        table = self.query_one("#libsearch-table", DataTable)
        table.clear()
        for item in self._filtered[:_MAX_ROWS]:
            table.add_row(item.library, item.name, key=item.reference)
        self.query_one("#libsearch-status", Label).update(self._status_text())

    def _run_filter(self) -> None:
        query = self.query_one("#libsearch-input", Input).value.strip().lower()
        if not query:
            self._filtered = list(self._items)
        else:
            self._filtered = [
                item for item in self._items if query in item.reference.lower()
            ]
        self._populate_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "libsearch-input":
            return
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(_DEBOUNCE_S, self._run_filter)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "libsearch-table":
            return
        ref = str(event.row_key.value)
        self.dismiss(ref)

    def action_cancel(self) -> None:
        self.dismiss(None)
