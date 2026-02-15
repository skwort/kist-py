"""
Library index builder.

Scans KiCad's installed library directories to build a searchable
catalog of footprints and symbols.  Footprints are indexed by directory
listing (fast); symbols are parsed via :class:`SymbolLibrary`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

from kist.kicad.discovery import KiCadEnvironment, parse_lib_table, resolve_uri
from kist.kicad.symbols import SymbolLibrary
from kist.models.config import LibraryConfig

log = logging.getLogger(__name__)

# -- Data types ---


@dataclass
class LibraryItem:
    """A single footprint or symbol from a library."""

    library: str  # e.g. "Resistor_SMD"
    name: str  # e.g. "R_0603_1608Metric"
    source: str  # "kicad" | "kist" | "3rdparty"

    @property
    def reference(self) -> str:
        """Full KiCad reference string: ``Library:Name``."""
        return f"{self.library}:{self.name}"


@dataclass
class LibraryIndex:
    """Combined index of all discovered footprints and symbols."""

    footprints: list[LibraryItem]
    symbols: list[LibraryItem]


# -- Footprint indexing ---


def build_footprint_index(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> list[LibraryItem]:
    """
    Build a footprint index from KiCad's ``fp-lib-table`` and kist's own footprints.

    Footprint indexing is fast -- just list ``.kicad_mod`` files inside
    each ``.pretty`` directory.  No file parsing needed.
    """
    items: list[LibraryItem] = []

    # KiCad global footprint libraries
    fp_table = env.config_dir / "fp-lib-table"
    for entry in parse_lib_table(fp_table):
        lib_path = resolve_uri(entry.uri, env)
        if lib_path.is_dir():
            for mod_file in sorted(lib_path.glob("*.kicad_mod")):
                items.append(
                    LibraryItem(
                        library=entry.name,
                        name=mod_file.stem,
                        source="kicad",
                    )
                )

    # Kist library footprints
    if kist_root and config:
        fp_dir = kist_root / config.footprints_dir
        if fp_dir.is_dir():
            for pretty_dir in sorted(fp_dir.glob("*.pretty")):
                lib_name = pretty_dir.stem
                for mod_file in sorted(pretty_dir.glob("*.kicad_mod")):
                    items.append(
                        LibraryItem(
                            library=lib_name,
                            name=mod_file.stem,
                            source="kist",
                        )
                    )

    return items


# -- Symbol indexing ---


def build_symbol_index(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> list[LibraryItem]:
    """
    Build a symbol index from KiCad's ``sym-lib-table`` and kist's own symbols.

    Parses each ``.kicad_sym`` file using :class:`SymbolLibrary` to
    extract symbol names.
    """
    items: list[LibraryItem] = []

    # KiCad global symbol libraries
    sym_table = env.config_dir / "sym-lib-table"
    for entry in parse_lib_table(sym_table):
        sym_path = resolve_uri(entry.uri, env)
        if sym_path.is_file():
            try:
                lib = SymbolLibrary.load(sym_path)
                for name in lib.symbols():
                    items.append(
                        LibraryItem(
                            library=entry.name,
                            name=name,
                            source="kicad",
                        )
                    )
            except Exception:
                log.warning("Failed to parse symbol library: %s", sym_path)

    # Kist library symbols
    if kist_root and config:
        sym_dir = kist_root / config.symbols_dir
        if sym_dir.is_dir():
            for sym_file in sorted(sym_dir.glob("*.kicad_sym")):
                try:
                    lib = SymbolLibrary.load(sym_file)
                    for name in lib.symbols():
                        items.append(
                            LibraryItem(
                                library=sym_file.stem,
                                name=name,
                                source="kist",
                            )
                        )
                except Exception:
                    log.warning("Failed to parse kist symbol library: %s", sym_file)

    return items


# -- Caching ---


def _cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("kist"))


def _cache_key(env: KiCadEnvironment) -> str:
    """Hash the lib-table mtimes to detect changes."""
    parts: list[str] = []
    for table_name in ("fp-lib-table", "sym-lib-table"):
        table_path = env.config_dir / table_name
        if table_path.is_file():
            mtime = table_path.stat().st_mtime
            parts.append(f"{table_path}:{mtime}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _save_cache(index: LibraryIndex, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "footprints": [asdict(item) for item in index.footprints],
        "symbols": [asdict(item) for item in index.symbols],
    }
    cache_path.write_text(json.dumps(data), encoding="utf-8")


def _load_cache(cache_path: Path) -> LibraryIndex | None:
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return LibraryIndex(
            footprints=[LibraryItem(**item) for item in data["footprints"]],
            symbols=[LibraryItem(**item) for item in data["symbols"]],
        )
    except Exception:
        return None


def load_or_build_index(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
    cache_dir: Path | None = None,
) -> LibraryIndex:
    """
    Load the library index from cache, or build and cache it.

    The cache is keyed on the mtimes of the global lib-table files.
    """
    if cache_dir is None:
        cache_dir = _cache_dir()

    key = _cache_key(env)
    cache_path = cache_dir / f"library_index_{key}.json"

    cached = _load_cache(cache_path)
    if cached is not None:
        return cached

    index = LibraryIndex(
        footprints=build_footprint_index(env, kist_root, config),
        symbols=build_symbol_index(env, kist_root, config),
    )

    _save_cache(index, cache_path)
    return index
