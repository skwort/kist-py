"""Browse screen -- library overview with category sidebar and parts table."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from textual import getters
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Static

from kist import __version__
from kist.core.database import PartsDatabase
from kist.models.part import Ipn, Part, ProprietaryPart, SemiJellybeanPart
from kist.tui.app import KistApp
from kist.tui.screens.detail import DetailModal
from kist.tui.widgets.category_list import CategoryList
from kist.tui.widgets.header import KistHeader
from kist.tui.widgets.parts_table import PartsTable

NO_LIBRARY_TEXT = (
    "No library found.\n\n"
    "Run [bold]kist init[/bold] to create one, or\n"
    "[bold]kist link <path>[/bold] to connect to an existing library."
)

EMPTY_LIBRARY_TEXT = (
    "\N{PACKAGE} Your library is empty.\n\n"
    "Add your first part:\n"
    "  [bold]kist add <url>[/bold]\n"
    "  [bold]ctrl+n[/bold] -- New part"
)


class BrowseScreen(Screen):
    """Main screen showing the parts library."""

    app = getters.app(KistApp)

    TITLE = "Kist"
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("slash", "focus_search", "Search", key_display="/"),
        Binding("ctrl+n", "new_part", "New part"),
    ]

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._all_parts: list[Part] = []
        self._selected_category: str | None = None
        self._search_query: str = ""

    def compose(self) -> ComposeResult:
        yield KistHeader(icon="\N{PACKAGE}", page_title="Browse")
        with Horizontal():
            yield CategoryList(id="sidebar")
            with Vertical(id="main-panel"):
                yield Input(placeholder="Search...", id="search")
                yield PartsTable(id="parts-table")
                yield Static(NO_LIBRARY_TEXT, id="empty-state", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.watch(self.app, "library_path", self._on_library_changed)
        self.watch(self.app, "parts_version", self._on_parts_changed)

    def _on_library_changed(self, path: Path | None) -> None:
        """React to the app discovering (or losing) a library."""
        if path is None:
            self._all_parts = []
            self._show_empty_state(NO_LIBRARY_TEXT)
            self.query_one("#sidebar", CategoryList).populate({})
            return

        db = PartsDatabase(path / "parts.json")
        try:
            db.load()
        except Exception:
            self._all_parts = []
            self._show_empty_state(NO_LIBRARY_TEXT)
            self.query_one("#sidebar", CategoryList).populate({})
            return

        self._all_parts = db.list_parts()

        # Build category counts
        counts: Counter[str] = Counter()
        for part in self._all_parts:
            counts[part.category] += 1

        self.query_one("#sidebar", CategoryList).populate(dict(counts))

        if not self._all_parts:
            self._show_empty_state(EMPTY_LIBRARY_TEXT)
        else:
            self._apply_filters()

    # -- Filtering -------------------------------------------------------------

    def _apply_filters(self) -> None:
        """Filter parts by selected category and search query, update table."""
        filtered = self._all_parts

        if self._selected_category is not None:
            filtered = [p for p in filtered if p.category == self._selected_category]

        if self._search_query:
            q = self._search_query.lower()
            filtered = [p for p in filtered if self._matches(p, q)]

        table = self.query_one("#parts-table", PartsTable)
        empty = self.query_one("#empty-state", Static)

        if filtered:
            table.display = True
            empty.display = False
            table.populate(filtered)
        else:
            table.display = False
            empty.display = True
            if self._all_parts:
                empty.update("No parts match the current filter.")
            else:
                empty.update(EMPTY_LIBRARY_TEXT)

    @staticmethod
    def _matches(part: Part, query: str) -> bool:
        """Substring match -- mirrors PartsDatabase._matches()."""
        if query in part.name.lower():
            return True
        if query in part.description.lower():
            return True
        if any(query in tag.lower() for tag in part.tags):
            return True
        if isinstance(part, (ProprietaryPart, SemiJellybeanPart)):
            if query in part.mpn.lower():
                return True
        if isinstance(part, SemiJellybeanPart):
            if query in part.base_pn.lower():
                return True
        return False

    # -- Empty state toggle ----------------------------------------------------

    def _show_empty_state(self, text: str) -> None:
        table = self.query_one("#parts-table", PartsTable)
        empty = self.query_one("#empty-state", Static)
        table.display = False
        empty.display = True
        empty.update(text)

    # -- Event handlers --------------------------------------------------------

    def on_category_list_selected(self, event: CategoryList.Selected) -> None:
        self._selected_category = event.category
        self._apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._search_query = event.value
            self._apply_filters()

    def on_data_table_row_selected(self, event: PartsTable.RowSelected) -> None:
        ipn = Ipn(str(event.row_key.value))
        part = next((p for p in self._all_parts if p.ipn == ipn), None)
        if part:
            self.app.push_screen(DetailModal(part))

    def _on_parts_changed(self, version: int) -> None:
        """Reload parts when the app signals a mutation."""
        if self.app.library_path:
            self._on_library_changed(self.app.library_path)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_new_part(self) -> None:
        """Open the add-part screen."""
        from kist.tui.screens.add import AddScreen

        self.app.push_screen(AddScreen())

    def on_key(self, event) -> None:
        """Clear search and refocus table on Escape from search input."""
        if event.key == "escape":
            search = self.query_one("#search", Input)
            if search.has_focus:
                search.value = ""
                self.query_one("#parts-table", PartsTable).focus()
                event.prevent_default()
