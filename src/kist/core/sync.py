"""Sync parts database to KiCad symbol library files."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from kist.core.database import PartsDatabase
from kist.kicad.lib_table import generate_sym_lib_table, update_sym_lib_table
from kist.kicad.mapping import library_filename
from kist.kicad.symbols import SymbolLibrary, get_visible_properties
from kist.kicad.templates import spec_property_key, symbol_for_part
from kist.models.config import LibraryConfig

SYM_LIB_TABLE = "sym-lib-table"


def sync_symbols(
    library_root: Path,
    db: PartsDatabase,
    config: LibraryConfig,
) -> list[Path]:
    """
    Push part metadata from the PartsDatabase to .kicad_sym files.

    Groups parts by category. For each category with parts, loads or
    creates a SymbolLibrary, generates symbols via symbol_for_part(),
    and saves. Idempotent.

    Returns the list of .kicad_sym files written.
    """
    symbols_dir = library_root / config.symbols_dir
    symbols_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

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
            existing = lib.get_symbol(part.name)
            visible = None
            if existing:
                visible_props = get_visible_properties(existing)
                spec_props = {
                    spec_property_key(spec_key)
                    for spec_key in (part.specifications or {})
                }
                visible = visible_props & spec_props
            lib.set_symbol(
                part.name,
                symbol_for_part(part, config.categories, visible_specs=visible),
            )

        lib.save(path)
        written.append(path)

    return written


def sync_sym_lib_table(
    project_dir: Path,
    symbol_files: list[Path],
    config: LibraryConfig,
) -> None:
    """
    Write or update the sym-lib-table in *project_dir*.

    If a sym-lib-table already exists, kist-managed entries are
    replaced while preserving non-kist entries. Otherwise a fresh
    table is generated.
    """
    table_path = project_dir / SYM_LIB_TABLE

    if table_path.exists():
        existing = table_path.read_text(encoding="utf-8")
        content = update_sym_lib_table(
            existing,
            symbol_files,
            config.symbols_dir,
            config.library_prefix,
            config.separator,
        )
    else:
        content = generate_sym_lib_table(
            symbol_files,
            config.symbols_dir,
            config.library_prefix,
            config.separator,
        )

    table_path.write_text(content, encoding="utf-8", newline="\n")
