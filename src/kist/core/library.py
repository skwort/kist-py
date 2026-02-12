"""Library operations: init, link, and discovery."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from kist.core.config import (
    KIST_MARKER,
    PROJECT_REF,
    load_project_ref,
    resolve_init_config,
    save_library_config,
    save_project_ref,
)
from kist.core.database import create_empty
from kist.errors import LibraryExistsError, LibraryNotFoundError
from kist.models.config import ProjectRef


def init_library(
    path: Path,
    *,
    symbols_dir: str | None = None,
    footprints_dir: str | None = None,
    models_dir: str | None = None,
    blocks_dir: str | None = None,
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

    rel_path = str(os.path.relpath(library, target))
    save_project_ref(ref_path, ProjectRef(library_path=rel_path))

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


def find_library(start: Path | None = None) -> Path:
    """
    Walk up from *start* to find the nearest kist library.

    Returns the library root directory.
    """
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / KIST_MARKER).is_dir():
            return current

        ref_path = current / PROJECT_REF
        if ref_path.is_file():
            ref = load_project_ref(ref_path)
            library = (current / ref.library_path).resolve()
            if (library / KIST_MARKER).is_dir():
                return library
            raise LibraryNotFoundError(
                f"{ref_path} points to {ref.library_path}, "
                f"but {library} is not a kist library."
            )

        parent = current.parent
        if parent == current:
            # Reached filesystem root (Path("/").parent == Path("/"))
            raise LibraryNotFoundError(
                f"Not a kist library (or any parent up to {current}).\n"
                "Run 'kist init' to create a new library, or\n"
                "'kist link <path>' to link to an existing one."
            )
        current = parent
