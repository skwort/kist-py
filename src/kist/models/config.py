"""Configuration models for library, global, and project-level config."""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_SUPPLIERS: list[str] = [
    "digikey",
    "mouser",
    "lcsc",
]


class CategoryDef(BaseModel):
    """
    Definition of a single part category.

    Stored in library config under ``[categories.CODE]``.
    """

    name: str
    refdes: str
    key_specs: list[str] = []
    subcategory_key_specs: dict[str, list[str]] = {}
    subcategory_names: dict[str, str] = {}
    value_field: str | list[str] | None = None
    subcategory_value_field: dict[str, str | list[str]] = {}
    value_field_separator: str = "/"
    symbol_template: str | None = None


class LibraryConfig(BaseModel):
    """Per-library config, always has concrete values -- resolved at init time."""

    version: int = 1
    library_id: str = ""
    library_prefix: str = "00k"
    separator: str = "-"
    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = list(DEFAULT_SUPPLIERS)
    digikey_locale: str = "US"
    digikey_currency: str = "USD"
    categories: dict[str, CategoryDef] = {}


class DigiKeyProviderConfig(BaseModel):
    """DigiKey API credentials and settings."""

    enabled: bool = True
    client_id: str | None = None
    client_secret: str | None = None


class ProvidersConfig(BaseModel):
    """Per-provider configuration, nested under GlobalConfig."""

    digikey: DigiKeyProviderConfig = DigiKeyProviderConfig()


class GlobalConfig(BaseModel):
    """User-level defaults. All fields optional with built-in defaults."""

    theme: str = "kist-dark"
    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = list(DEFAULT_SUPPLIERS)
    providers: ProvidersConfig = ProvidersConfig()


class ProjectRef(BaseModel):
    """Project-level reference pointing to a library root."""

    version: int = 1
    library_path: str
    library_id: str = ""
