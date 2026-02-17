"""
Library index builder.

Scans KiCad's installed library directories to build a searchable
catalog of footprints and symbols.  Footprints are indexed by directory
listing (fast); symbols use a lightweight regex scan to extract
top-level symbol names without full S-expression parsing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

from kist.kicad.discovery import KiCadEnvironment, parse_lib_table, resolve_uri
from kist.kicad.symbols import SymbolLibrary
from kist.models.config import LibraryConfig

log = logging.getLogger(__name__)

# Top-level symbol names in .kicad_sym files: one tab indent, then (symbol "NAME"
# This avoids full S-expression parsing (~50x faster for 225 libraries).
_SYMBOL_NAME_RE = re.compile(r'^\t\(symbol\s+"([^"]+)"', re.MULTILINE)


def _scan_symbol_names(path: Path) -> list[str]:
    """Extract top-level symbol names from a .kicad_sym file via regex."""
    text = path.read_text(encoding="utf-8")
    return _SYMBOL_NAME_RE.findall(text)


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

    Uses a lightweight regex scan to extract top-level symbol names
    from ``.kicad_sym`` files without full S-expression parsing.
    """
    items: list[LibraryItem] = []

    # KiCad global symbol libraries
    sym_table = env.config_dir / "sym-lib-table"
    for entry in parse_lib_table(sym_table):
        sym_path = resolve_uri(entry.uri, env)
        if sym_path.is_file():
            try:
                for name in _scan_symbol_names(sym_path):
                    items.append(
                        LibraryItem(
                            library=entry.name,
                            name=name,
                            source="kicad",
                        )
                    )
            except Exception:
                log.warning("Failed to scan symbol library: %s", sym_path)

    # Kist library symbols
    if kist_root and config:
        sym_dir = kist_root / config.symbols_dir
        if sym_dir.is_dir():
            for sym_file in sorted(sym_dir.glob("*.kicad_sym")):
                try:
                    for name in _scan_symbol_names(sym_file):
                        items.append(
                            LibraryItem(
                                library=sym_file.stem,
                                name=name,
                                source="kist",
                            )
                        )
                except Exception:
                    log.warning("Failed to scan kist symbol library: %s", sym_file)

    return items


def _symbol_paths_for_library(
    library: str,
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> list[Path]:
    """Return candidate .kicad_sym files for a logical symbol library name."""
    paths: list[Path] = []
    seen: set[Path] = set()

    sym_table = env.config_dir / "sym-lib-table"
    for entry in parse_lib_table(sym_table):
        if entry.name != library:
            continue
        sym_path = resolve_uri(entry.uri, env)
        if sym_path.is_file() and sym_path not in seen:
            paths.append(sym_path)
            seen.add(sym_path)

    if kist_root and config:
        kist_sym_path = kist_root / config.symbols_dir / f"{library}.kicad_sym"
        if kist_sym_path.is_file() and kist_sym_path not in seen:
            paths.append(kist_sym_path)

    return paths


def _linked_footprint_from_symbol_file(path: Path, symbol: str) -> str | None:
    """Extract non-empty Footprint property for one symbol in one library file."""
    try:
        lib = SymbolLibrary.load(path)
        sym = lib.get_symbol(symbol)
        if sym is None:
            return None
        for child in sym:
            if (
                isinstance(child, list)
                and len(child) > 2
                and child[0] == "property"
                and str(child[1]) == "Footprint"
            ):
                footprint = str(child[2]).strip()
                return footprint or None
    except Exception:
        log.warning("Failed to resolve linked footprint from symbol library: %s", path)
    return None


def linked_footprint_for_symbol(
    symbol_ref: str,
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> str | None:
    """
    Resolve a symbol reference's linked footprint from KiCad symbol properties.

    ``symbol_ref`` must be in ``Library:Symbol`` format.
    """
    if ":" not in symbol_ref:
        return None
    library, symbol = symbol_ref.split(":", 1)
    if not library or not symbol:
        return None

    paths = _symbol_paths_for_library(library, env, kist_root, config)
    for path in paths:
        linked = _linked_footprint_from_symbol_file(path, symbol)
        if linked:
            return linked
    return None


# -- Caching ---


def _cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("kist"))


def _iter_kist_fingerprint_parts(
    kist_root: Path | None,
    config: LibraryConfig | None,
) -> list[str]:
    """Build fingerprint parts for kist-managed symbols/footprints."""
    if kist_root is None or config is None:
        return []

    parts: list[str] = []
    config_path = kist_root / ".kist" / "config.toml"
    if config_path.is_file():
        stat = config_path.stat()
        parts.append(f"{config_path}:{stat.st_mtime_ns}:{stat.st_size}")

    sym_dir = kist_root / config.symbols_dir
    if sym_dir.is_dir():
        for sym_file in sorted(sym_dir.glob("*.kicad_sym")):
            stat = sym_file.stat()
            parts.append(f"{sym_file}:{stat.st_mtime_ns}:{stat.st_size}")

    fp_dir = kist_root / config.footprints_dir
    if fp_dir.is_dir():
        for mod_file in sorted(fp_dir.glob("*.pretty/*.kicad_mod")):
            stat = mod_file.stat()
            parts.append(f"{mod_file}:{stat.st_mtime_ns}:{stat.st_size}")

    return parts


def _cache_key(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> str:
    """Hash lib-table mtimes and resolved variable paths to detect changes.

    Including the resolved paths ensures the cache invalidates when
    variables change (e.g. Nix store path update, env var override).
    """
    parts: list[str] = []
    for table_name in ("fp-lib-table", "sym-lib-table"):
        table_path = env.config_dir / table_name
        if table_path.is_file():
            mtime = table_path.stat().st_mtime
            parts.append(f"{table_path}:{mtime}")
    for var_name in sorted(env.variables):
        parts.append(f"{var_name}={env.variables[var_name]}")
    parts.extend(_iter_kist_fingerprint_parts(kist_root, config))
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

    key = _cache_key(env, kist_root, config)
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
