"""
KiCad installation discovery.

Finds KiCad's config and data directories, parses the global
``fp-lib-table`` and ``sym-lib-table`` to get library names and URIs,
and resolves ``${KICAD9_FOOTPRINT_DIR}`` style variables to real paths.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from kist.sexpr import find_all, parse_one

# -- Data types ---


@dataclass
class LibTableEntry:
    """A single row from a KiCad lib table (fp-lib-table or sym-lib-table)."""

    name: str
    uri: str
    lib_type: str = "KiCad"


@dataclass
class KiCadEnvironment:
    """Detected KiCad installation paths and variable mappings."""

    version: str  # e.g. "9.0"
    config_dir: Path  # e.g. ~/.config/kicad/9.0
    data_dir: Path  # e.g. ~/.local/share/kicad/9.0
    variables: dict[str, Path] = field(default_factory=dict)


# -- Detection ---

_VERSION_RE = re.compile(r"^(\d+\.\d+)$")


def _probe_versioned_dirs(base: Path) -> list[str]:
    """Return version strings found under *base*, sorted descending."""
    if not base.is_dir():
        return []
    versions = []
    for child in base.iterdir():
        if child.is_dir() and _VERSION_RE.match(child.name):
            versions.append(child.name)
    return sorted(
        versions, key=lambda v: tuple(int(x) for x in v.split(".")), reverse=True
    )


def _major(version: str) -> int:
    """Extract major version number: '9.0' -> 9."""
    return int(version.split(".")[0])


def _build_variables(version: str, data_dir: Path) -> dict[str, Path]:
    """
    Build the KiCad variable map for a given version.

    Checks environment variable overrides first, then falls back to
    the conventional data directory layout.
    """
    major = _major(version)
    mapping: dict[str, Path] = {}

    var_defs = {
        f"KICAD{major}_FOOTPRINT_DIR": data_dir / "footprints",
        f"KICAD{major}_SYMBOL_DIR": data_dir / "symbols",
        f"KICAD{major}_3DMODEL_DIR": data_dir / "3dmodels",
        f"KICAD{major}_TEMPLATE_DIR": data_dir / "template",
    }

    for var_name, default_path in var_defs.items():
        env_val = os.environ.get(var_name)
        if env_val:
            mapping[var_name] = Path(env_val)
        else:
            mapping[var_name] = default_path

    return mapping


def detect_kicad() -> KiCadEnvironment | None:
    """
    Detect the KiCad installation by probing for versioned config dirs.

    Returns the environment for the highest version found, or ``None``
    if no KiCad config directory exists.
    """
    config_base = Path(platformdirs.user_config_dir("kicad"))
    data_base = Path(platformdirs.user_data_dir("kicad"))

    versions = _probe_versioned_dirs(config_base)
    if not versions:
        return None

    version = versions[0]  # highest
    config_dir = config_base / version
    data_dir = data_base / version
    variables = _build_variables(version, data_dir)

    return KiCadEnvironment(
        version=version,
        config_dir=config_dir,
        data_dir=data_dir,
        variables=variables,
    )


# -- Variable resolution ---

_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_uri(uri: str, env: KiCadEnvironment) -> Path:
    """
    Resolve a KiCad URI by substituting ``${VAR}`` references.

    Variables are looked up in *env.variables*.  Unresolved variables
    are left as-is (the path will likely not exist, which callers can
    handle).
    """

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        resolved = env.variables.get(var_name)
        if resolved is not None:
            return str(resolved)
        # Check environment directly as fallback
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        return match.group(0)

    return Path(_VAR_RE.sub(_replace, uri))


# -- Lib table parsing ---


def parse_lib_table(path: Path) -> list[LibTableEntry]:
    """
    Parse a KiCad ``fp-lib-table`` or ``sym-lib-table`` file.

    Returns a list of :class:`LibTableEntry` with name, URI, and type
    for each ``(lib ...)`` row.
    """
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    tree = parse_one(text)

    if not isinstance(tree, list) or not tree:
        return []

    entries: list[LibTableEntry] = []
    for lib in find_all(tree, "lib"):
        name = ""
        uri = ""
        lib_type = "KiCad"
        for child in lib[1:]:
            if not isinstance(child, list) or len(child) < 2:
                continue
            tag = child[0]
            val = str(child[1])
            if tag == "name":
                name = val
            elif tag == "uri":
                uri = val
            elif tag == "type":
                lib_type = val
        if name:
            entries.append(LibTableEntry(name=name, uri=uri, lib_type=lib_type))

    return entries
