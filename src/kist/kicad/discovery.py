"""
KiCad installation discovery.

Finds KiCad's config and data directories, parses the global
``fp-lib-table`` and ``sym-lib-table`` to get library names and URIs,
and resolves ``${KICAD9_FOOTPRINT_DIR}`` style variables to real paths.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from kist.sexpr import find_all, parse_one

log = logging.getLogger(__name__)

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


_NIX_EXPORT_RE = re.compile(
    r"^export\s+(KICAD\d+_\w+_DIR)=\$\{[^-]+-'([^']+)'\}",
)


def _nix_kicad_variables() -> dict[str, Path]:
    """
    Extract KiCad variable defaults from a Nix wrapper script.

    On NixOS / nix-managed installs, the ``kicad`` binary is a bash
    wrapper that sets ``KICAD9_FOOTPRINT_DIR`` etc. with Nix store
    paths as defaults.  Returns those paths, or an empty dict if
    KiCad is not a Nix wrapper.
    """
    kicad_bin = shutil.which("kicad")
    if kicad_bin is None:
        return {}

    bin_path = Path(kicad_bin)
    resolved = bin_path.resolve()
    if "/nix/store/" not in str(bin_path) and "/nix/store/" not in str(resolved):
        return {}

    # It's a Nix binary -- read the wrapper script for variable defaults
    try:
        wrapper_text = Path(kicad_bin).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    variables: dict[str, Path] = {}
    for line in wrapper_text.splitlines():
        m = _NIX_EXPORT_RE.match(line.strip())
        if m:
            var_name, nix_path = m.group(1), m.group(2)
            p = Path(nix_path)
            if p.is_dir():
                variables[var_name] = p

    if variables:
        log.debug("Discovered Nix KiCad variables: %s", list(variables.keys()))

    return variables


def _build_variables(version: str, data_dir: Path) -> dict[str, Path]:
    """
    Build the KiCad variable map for a given version.

    Resolution order for each variable:
    1. Environment variable override (user explicitly set it)
    2. Conventional data directory (``~/.local/share/kicad/9.0/...``)
    3. Nix wrapper defaults (if the conventional path doesn't exist
       and KiCad is installed via Nix)
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

    # If key directories are missing or empty, check for Nix wrapper overrides.
    # KiCad may create empty dirs at ~/.local/share/kicad/9.0/footprints/
    # while the actual libraries live in the Nix store.
    def _dir_has_content(p: Path) -> bool:
        return p.is_dir() and any(p.iterdir())

    needs_nix = any(
        not _dir_has_content(mapping[v])
        for v in (f"KICAD{major}_FOOTPRINT_DIR", f"KICAD{major}_SYMBOL_DIR")
        if v in mapping
    )
    if needs_nix:
        nix_vars = _nix_kicad_variables()
        for var_name, nix_path in nix_vars.items():
            if var_name in mapping and not _dir_has_content(mapping[var_name]):
                mapping[var_name] = nix_path

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
