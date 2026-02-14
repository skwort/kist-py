"""Library operations: init, link, and discovery."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import NamedTuple

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.config import (
    KIST_MARKER,
    PROJECT_REF,
    load_library_config,
    load_project_ref,
    resolve_init_config,
    save_library_config,
    save_project_ref,
)
from kist.core.database import create_empty
from kist.errors import ConfigError, LibraryExistsError, LibraryNotFoundError
from kist.models.config import CategoryDef, ProjectRef


class DiscoveryResult(NamedTuple):
    """Result of library discovery, with optional project context."""

    library_root: Path
    project_dir: Path | None = None


def init_library(
    path: Path,
    *,
    symbols_dir: str | None = None,
    footprints_dir: str | None = None,
    models_dir: str | None = None,
    blocks_dir: str | None = None,
    categories: dict[str, CategoryDef] | None = None,
) -> Path:
    """
    Create a new kist library at *path*.

    Returns the resolved path to the library root.
    """
    path = path.resolve()
    kist_dir = path / KIST_MARKER

    if kist_dir.exists():
        raise LibraryExistsError(f"Already initialised: {path}")

    config = resolve_init_config(
        symbols_dir=symbols_dir,
        footprints_dir=footprints_dir,
        models_dir=models_dir,
        blocks_dir=blocks_dir,
    )
    config.library_id = str(uuid.uuid4())
    config.categories = (
        categories if categories is not None else dict(WELL_KNOWN_CATEGORIES)
    )
    save_library_config(path, config)

    parts_json = path / "parts.json"
    if not parts_json.exists():
        create_empty(parts_json)

    for subdir in (
        config.symbols_dir,
        config.footprints_dir,
        config.models_dir,
        config.blocks_dir,
    ):
        (path / subdir).mkdir(parents=True, exist_ok=True)

    return path


def link_library(target: Path, library: Path) -> Path:
    """
    Connect a project directory to an existing kist library.

    Returns the path to the created kist.toml.
    """
    target = target.resolve()
    library = library.resolve()

    if not (library / KIST_MARKER).is_dir():
        raise LibraryNotFoundError(f"Not a kist library: {library}")

    ref_path = target / PROJECT_REF
    if ref_path.exists():
        raise LibraryExistsError(f"Already linked: {ref_path}")

    lib_config = load_library_config(library)
    rel_path = str(os.path.relpath(library, target))
    save_project_ref(
        ref_path,
        ProjectRef(library_path=rel_path, library_id=lib_config.library_id),
    )

    _create_lib_link(target / "lib", rel_path)

    return ref_path


def _create_lib_link(link: Path, target: str) -> None:
    """Create a lib/ link for KiCad's ${KIPRJMOD}/lib/ convention.

    Uses a symlink on Unix. On Windows, uses a directory junction which
    doesn't require admin privileges or Developer Mode.

    Non-fatal -- kist itself only needs kist.toml to find the library;
    the link is a convenience for KiCad path resolution.
    """
    if link.exists():
        return
    try:
        if sys.platform == "win32":
            # Junction: no elevation required, works for local directories
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), target],
                check=True,
                capture_output=True,
            )
        else:
            link.symlink_to(target)
    except (OSError, subprocess.CalledProcessError):
        pass


def find_library(start: Path | None = None) -> DiscoveryResult:
    """
    Walk up from *start* to find the nearest kist library.

    Returns a :class:`DiscoveryResult` with the library root and,
    when discovered via a project reference (``kist.toml``), the
    project directory.

    When the library is found directly (via ``.kist/``), also checks
    the parent directory for a ``kist.toml`` that points back to it,
    so ``kist sync`` works from inside the library.
    """
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / KIST_MARKER).is_dir():
            project_dir = _find_project_for_library(current)
            return DiscoveryResult(current, project_dir)

        ref_path = current / PROJECT_REF
        if ref_path.is_file():
            ref = load_project_ref(ref_path)
            library = (current / ref.library_path).resolve()
            if (library / KIST_MARKER).is_dir():
                return DiscoveryResult(library, current)
            raise LibraryNotFoundError(
                f"{ref_path} points to {ref.library_path}, "
                f"but {library} is not a kist library."
            )

        parent = current.parent
        if parent == current:
            raise LibraryNotFoundError(
                f"Not a kist library (or any parent up to {current}).\n"
                "Run 'kist init' to create a new library, or\n"
                "'kist link <path>' to link to an existing one."
            )
        current = parent


def _find_project_for_library(library_root: Path) -> Path | None:
    """
    Check the parent directory for a ``kist.toml`` pointing to *library_root*.

    Handles the single-board case where the library is at ``project/lib/``
    and the project ref is at ``project/kist.toml``.
    """
    parent = library_root.parent
    ref_path = parent / PROJECT_REF
    if not ref_path.is_file():
        return None
    try:
        ref = load_project_ref(ref_path)
    except ConfigError:
        return None
    resolved = (parent / ref.library_path).resolve()
    if resolved == library_root:
        return parent
    return None
