"""Library search modal -- fzf-style search for footprints and symbols."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Input, Label, Select, Static

from kist.kicad.indexer import LibraryItem
from kist.kicad.render import RenderTheme
from kist.tui.themes import render_theme_from_textual

log = logging.getLogger(__name__)

_MAX_ROWS = 200
_DEBOUNCE_S = 0.15

# textual_image must be pre-imported in run_tui() before Textual starts,
# so that its terminal probe (get_cell_size) doesn't dump escape codes.
_ImageWidget: type | None = None


def _preview_available() -> bool:
    """Check if textual_image is importable."""
    global _ImageWidget  # noqa: PLW0603
    if _ImageWidget is not None:
        return True
    try:
        from textual_image.widget import Image

        _ImageWidget = Image
        return True
    except ImportError:
        return False


@lru_cache(maxsize=8)
def _load_symbol_library(path: Path, mtime_ns: int):
    """Cached load of a .kicad_sym file, invalidated by mtime."""
    del mtime_ns  # cache key only
    from kist.kicad.symbols import SymbolLibrary

    return SymbolLibrary.load(path)


LibrarySearchResult = str | tuple[Literal["clone"], str] | None


class LibrarySearchModal(ModalScreen[LibrarySearchResult]):
    """
    Search and select a library item (footprint or symbol).

    Presents an input at the top with filtered results below.
    Substring matching on the full ``Library:Name`` reference.
    Dismisses with the selected reference string, or ``None`` on cancel.

    Pass *items* to populate immediately, or omit to load the index
    asynchronously (the modal opens instantly and shows a loading state).
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "clone", "Clone to local"),
    ]

    def __init__(
        self,
        items: list[LibraryItem] | None = None,
        title: str = "Footprints",
        item_kind: Literal["symbol", "footprint"] | None = None,
        initial_value: str = "",
    ) -> None:
        super().__init__()
        self._items: list[LibraryItem] = items or []
        self._title = title
        self._filtered: list[LibraryItem] = list(self._items)
        self._loading = items is None
        self._debounce_timer: Timer | None = None
        self._initial_value = initial_value

        if item_kind is not None:
            self._item_kind = item_kind
        elif title.lower() == "symbols":
            self._item_kind = "symbol"
        else:
            self._item_kind = "footprint"

        self._sym_paths: dict[str, Path] = {}
        self._fp_paths: dict[str, Path] = {}
        self._has_preview = _preview_available()
        self._preview_ready = False
        self._preview_seq = 0
        self._render_theme = RenderTheme()

        # Multi-unit symbol state.
        self._current_ref: str | None = None
        self._current_units: list[int] = [1]
        self._current_unit: int = 1

    def compose(self) -> ComposeResult:
        with Horizontal(id="libsearch-outer"):
            with Vertical(id="libsearch-container") as container:
                container.border_title = self._title
                yield Input(placeholder="Type to search...", id="libsearch-input")
                yield Label(self._status_text(), id="libsearch-status")
                yield DataTable(id="libsearch-table")
            if self._has_preview:
                with Vertical(id="libsearch-preview") as preview:
                    preview.border_title = "Preview"
                    yield Static("Select an item", id="preview-placeholder")
                    yield Select([], id="unit-select", prompt="Unit")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#libsearch-table", DataTable)
        table.add_columns("Library", "Name", "Source")
        table.cursor_type = "row"
        table.zebra_stripes = True

        self.query_one("#libsearch-input", Input).focus()

        if self._loading:
            self.query_one("#libsearch-status", Label).update(self._status_text())
            self._load_index()
        else:
            self._populate_table()
            self._scroll_to_value()
            self._init_preview()

    def _init_preview(self) -> None:
        if self._has_preview:
            self._render_theme = render_theme_from_textual(
                self.app.available_themes.get(self.app.theme)
            )
            self._hide_unit_select()
            self._build_path_lookups()

    @work(exclusive=True)
    async def _load_index(self) -> None:
        index = await asyncio.to_thread(self._fetch_index)
        if index is None:
            self.notify(
                "KiCad not found -- cannot browse libraries", severity="warning"
            )
            self.dismiss(None)
            return

        # Update app-level cache so subsequent opens are instant.
        if hasattr(self.app, "_library_index"):
            self.app._library_index = index  # type: ignore[attr-defined]

        items = index.symbols if self._item_kind == "symbol" else index.footprints
        if not items:
            self.notify(
                f"No {self._title.lower()} found in library index",
                severity="warning",
            )
            self.dismiss(None)
            return

        self._items = items
        self._filtered = list(items)
        self._loading = False
        self._populate_table()
        self._scroll_to_value()
        self._init_preview()

    def _fetch_index(self):
        """Build the library index (runs in worker thread)."""
        from kist.kicad.discovery import detect_kicad
        from kist.kicad.indexer import load_or_build_index

        # Use app cache if available.
        cached = getattr(self.app, "_library_index", None)
        if cached is not None:
            return cached

        env = detect_kicad()
        if env is None:
            return None

        try:
            return load_or_build_index(
                env,
                kist_root=getattr(self.app, "library_path", None),
                config=getattr(self.app, "library_config", None),
            )
        except Exception:
            log.warning("Failed to build library index", exc_info=True)
            return None

    def _build_path_lookups(self) -> None:
        """Build library-name -> file path mappings for preview."""
        try:
            from kist.kicad.discovery import detect_kicad
            from kist.kicad.render import (
                build_footprint_path_lookup,
                build_symbol_path_lookup,
            )

            env = detect_kicad()
            if env is None:
                self._set_preview_placeholder("KiCad environment not found")
                return

            kist_root = getattr(self.app, "library_path", None)
            config = getattr(self.app, "library_config", None)

            if self._item_kind == "symbol":
                self._sym_paths = build_symbol_path_lookup(env, kist_root, config)
                if not self._sym_paths:
                    self._set_preview_placeholder("No symbol libraries found")
                else:
                    self._preview_ready = True
            else:
                self._fp_paths = build_footprint_path_lookup(env, kist_root, config)
                if not self._fp_paths:
                    self._set_preview_placeholder("No footprint libraries found")
                else:
                    self._preview_ready = True
        except Exception:
            log.debug("Failed to build path lookups", exc_info=True)
            self._set_preview_placeholder("Preview unavailable")

    def _status_text(self) -> str:
        if self._loading:
            return f"Loading {self._title.lower()}..."
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
            table.add_row(item.library, item.name, item.source, key=item.reference)
        self.query_one("#libsearch-status", Label).update(self._status_text())

        if self._has_preview and table.row_count == 0:
            self._set_preview_placeholder("No matching items")
            self._hide_unit_select()
            self._current_ref = None

    def _scroll_to_value(self) -> None:
        """Move the matching item to the top of the list and select it."""
        if not self._initial_value:
            return
        for idx, item in enumerate(self._filtered):
            if item.reference == self._initial_value:
                if idx != 0:
                    self._filtered.insert(0, self._filtered.pop(idx))
                    self._populate_table()
                table = self.query_one("#libsearch-table", DataTable)
                table.move_cursor(row=0)
                return

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

    def _selected_ref(self) -> str | None:
        table = self.query_one("#libsearch-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if (
            event.data_table.id != "libsearch-table"
            or not self._has_preview
            or not self._preview_ready
        ):
            return
        if event.row_key is None or event.row_key.value is None:
            return

        ref = str(event.row_key.value)
        if ref == self._current_ref:
            return

        self._preview_seq += 1
        self._current_ref = ref
        self._set_preview_placeholder("Rendering preview...")
        self._render_preview_worker(ref, self._preview_seq)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "unit-select":
            return
        if event.value == Select.BLANK or self._current_ref is None:
            return
        if not isinstance(event.value, str):
            return

        try:
            unit = int(event.value)
        except (TypeError, ValueError):
            return

        if unit == self._current_unit:
            return

        self._current_unit = unit
        self._preview_seq += 1
        self._set_preview_placeholder("Rendering preview...")
        self._render_preview_worker(self._current_ref, self._preview_seq)

    @work(exclusive=True)
    async def _render_preview_worker(self, ref: str, seq: int) -> None:
        try:
            payload = await asyncio.to_thread(
                self._build_preview_payload, ref, self._current_unit
            )
        except Exception:
            log.debug("Preview render failed for %s", ref, exc_info=True)
            payload = {"error": "Preview unavailable"}
        self._apply_preview_payload(seq, ref, payload)

    def _build_preview_payload(self, ref: str, unit: int) -> dict[str, Any]:
        from kist.kicad.render import get_symbol_units, load_footprint, render_footprint

        try:
            library, name = ref.split(":", 1)
        except ValueError:
            return {"error": "Invalid item reference"}

        if self._item_kind == "symbol":
            sym_path = self._sym_paths.get(library)
            if sym_path is None or not sym_path.is_file():
                return {"error": "Symbol library not found"}

            stat = sym_path.stat()
            lib = _load_symbol_library(sym_path, stat.st_mtime_ns)
            sym = lib.get_symbol(name)
            if sym is None:
                return {"error": "Symbol not found"}

            units = get_symbol_units(sym)
            active_unit = unit if unit in units else units[0]

            from kist.kicad.render import render_symbol

            img = render_symbol(sym, unit=active_unit, theme=self._render_theme)
            return {
                "kind": "symbol",
                "image": img,
                "units": units,
                "active_unit": active_unit,
            }

        fp_dir = self._fp_paths.get(library)
        if fp_dir is None:
            return {"error": "Footprint library not found"}

        fp_path = fp_dir / f"{name}.kicad_mod"
        if not fp_path.is_file():
            return {"error": "Footprint file not found"}

        tree = load_footprint(fp_path)
        img = render_footprint(tree, theme=self._render_theme)
        return {
            "kind": "footprint",
            "image": img,
        }

    def _apply_preview_payload(
        self, seq: int, ref: str, payload: dict[str, Any]
    ) -> None:
        if seq != self._preview_seq or ref != self._current_ref:
            return

        error = payload.get("error")
        if isinstance(error, str):
            self._hide_unit_select()
            self._set_preview_placeholder(error)
            return

        image = payload.get("image")
        if image is None:
            self._hide_unit_select()
            self._set_preview_placeholder("Preview unavailable")
            return

        if payload.get("kind") == "symbol":
            units = payload.get("units")
            active = payload.get("active_unit")
            if isinstance(units, list) and all(isinstance(u, int) for u in units):
                self._current_units = units
            else:
                self._current_units = [1]

            if isinstance(active, int):
                self._current_unit = active

            self._update_unit_select()
        else:
            self._hide_unit_select()

        self._set_preview_image(image)

    def _update_unit_select(self) -> None:
        unit_select = self.query_one("#unit-select", Select)
        if len(self._current_units) <= 1:
            unit_select.display = False
            return

        options = [(f"Unit {u}", str(u)) for u in self._current_units]
        unit_select.set_options(options)
        unit_select.value = str(self._current_unit)
        unit_select.display = True

    def _hide_unit_select(self) -> None:
        if not self._has_preview:
            return
        self.query_one("#unit-select", Select).display = False

    def _set_preview_placeholder(self, text: str) -> None:
        if not self._has_preview:
            return

        preview = self.query_one("#libsearch-preview", Vertical)
        existing = self.query("#preview-image")
        for widget in existing:
            widget.remove()

        try:
            placeholder = self.query_one("#preview-placeholder", Static)
        except NoMatches:
            preview.mount(Static(text, id="preview-placeholder"))
            return
        placeholder.update(text)

    def _set_preview_image(self, image: Any) -> None:
        if not self._has_preview:
            return

        preview = self.query_one("#libsearch-preview", Vertical)

        placeholder = self.query("#preview-placeholder")
        for widget in placeholder:
            widget.remove()

        existing = self.query("#preview-image")
        if existing:
            existing[0].image = image  # type: ignore[attr-defined]
        elif _ImageWidget is not None:
            preview.mount(_ImageWidget(image, id="preview-image"))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_clone(self) -> None:
        ref = self._selected_ref()
        if ref is None:
            return
        self.dismiss(("clone", ref))
