"""Intermediate models for supplier provider responses."""

from __future__ import annotations

from pydantic import BaseModel


class DigiKeyProduct(BaseModel):
    """
    Normalised product data from the DigiKey v4 API.

    Fields are mapped from the raw API response so downstream code
    (TUI, part creation) doesn't depend on DigiKey's schema directly.
    """

    mpn: str
    manufacturer: str
    description: str
    detailed_description: str
    digikey_pn: str
    digikey_url: str | None = None
    datasheet_url: str | None = None
    category: str | None = None
    parameters: dict[str, str] = {}
    unit_price: float | None = None
    quantity_available: int | None = None
    package: str | None = None
    mounting: str | None = None
