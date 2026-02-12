"""Sync parts database to KiCad symbol library files."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kist.core.database import PartsDatabase
from kist.kicad.mapping import library_filename
from kist.kicad.symbols import SymbolLibrary
from kist.kicad.templates import symbol_for_part
from kist.models.config import LibraryConfig


def sync_symbols(
    library_root: Path,
    db: PartsDatabase,
    config: LibraryConfig,
) -> None:
    """
    Push part metadata from the PartsDatabase to .kicad_sym files.

    Groups parts by category. For each category with parts, loads or
    creates a SymbolLibrary, generates symbols via symbol_for_part(),
    and saves. Idempotent.
    """
    symbols_dir = library_root / config.symbols_dir
    symbols_dir.mkdir(parents=True, exist_ok=True)

    # Group parts by category
    by_category: dict[str, list] = defaultdict(list)
    for part in db.list_parts():
        by_category[part.category].append(part)

    for category_code, parts in by_category.items():
        cat_def = config.categories.get(category_code)
        cat_name = cat_def.name if cat_def else category_code
        path = symbols_dir / library_filename(
            cat_name, config.library_prefix, config.separator
        )

        if path.exists():
            lib = SymbolLibrary.load(path)
        else:
            lib = SymbolLibrary.empty()

        for part in parts:
            lib.set_symbol(part.name, symbol_for_part(part, config.categories))

        lib.save(path)
