"""Intermediate models for supplier provider responses."""

from __future__ import annotations

from pydantic import BaseModel


class ProviderMappingConfig(BaseModel):
    """
    Mapping configuration for a supplier provider.

    Controls how raw API responses are translated into ProviderProduct
    fields. Built-in defaults ship with each provider module; users can
    override via TOML in the config directory.

    The ``parameters`` dict maps raw API parameter names to normalised
    target names.  Only mapped parameters are kept (whitelist approach).
    Target names determine routing:

    - ``"package"`` and ``"mounting"`` are extracted to top-level
      ProviderProduct fields (and excluded from the parameters dict).
    - All other targets land in ``ProviderProduct.parameters``.
    - Parameters not in the map are dropped.

    The ``mounting`` dict normalises raw mounting values to canonical
    strings (e.g. ``"Surface Mount"`` --> ``"smd"``).
    """

    supplier_name: str = ""
    categories: dict[str, str] = {}
    parameters: dict[str, str] = {}
    mounting: dict[str, str] = {}


class ProviderProduct(BaseModel):
    """
    Normalised product data from a supplier API.

    Fields are mapped from the raw API response so downstream code
    (TUI, part creation) doesn't depend on any provider's schema.
    """

    mpn: str
    manufacturer: str
    description: str
    detailed_description: str
    supplier_name: str
    supplier_sku: str
    supplier_url: str | None = None
    datasheet_url: str | None = None
    category: str | None = None
    parameters: dict[str, str] = {}
    unit_price: float | None = None
    quantity_available: int | None = None
    package: str | None = None
    mounting: str | None = None
    # Environmental classifications
    rohs_status: str | None = None
    reach_status: str | None = None
