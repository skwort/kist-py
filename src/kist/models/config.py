"""Configuration models for library, global, and project-level config."""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_SUPPLIERS: list[str] = [
    "digikey",
    "mouser",
    "lcsc",
]


class LibraryConfig(BaseModel):
    """Per-library config, always has concrete values -- resolved at init time."""

    version: int = 1
    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = list(DEFAULT_SUPPLIERS)


class GlobalConfig(BaseModel):
    """User-level defaults. All fields optional with built-in defaults."""

    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = list(DEFAULT_SUPPLIERS)


class ProjectRef(BaseModel):
    """Project-level reference pointing to a library root."""

    version: int = 1
    library_path: str
