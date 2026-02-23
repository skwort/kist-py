"""Shared save logic for building a Part from form data."""

from __future__ import annotations

from kist.core.naming import generate_description, generate_name, generate_value
from kist.models.config import CategoryDef
from kist.models.part import (
    JellybeanPart,
    Part,
    ProprietaryPart,
    SemiJellybeanPart,
    SupplierInfo,
    Tier,
)


class ValidationNotice(Exception):
    """User-facing validation message raised during part construction."""


def build_part_from_form(
    d: dict,
    categories: dict[str, CategoryDef],
    separator: str = "-",
) -> Part:
    """
    Build a fully-named Part from a PartForm dict and library config.

    Validates required fields, constructs the tier-appropriate Part subclass,
    and generates name/value/description. Raises ``ValidationNotice`` for
    missing required fields.
    """
    tier = d.get("tier")
    if not tier:
        raise ValidationNotice("Tier is required")

    category = d.get("category")
    if not category:
        raise ValidationNotice("Category is required")

    # Build SupplierInfo objects from flat dicts
    suppliers = {
        name: SupplierInfo(sku=info["sku"], url=info.get("url"))
        for name, info in d.get("suppliers", {}).items()
    }

    cat_def = categories.get(category)
    reference = cat_def.refdes if cat_def else "U"

    # Normalise protocol-relative datasheet URLs
    datasheet = d.get("datasheet")
    if datasheet and datasheet.startswith("//"):
        datasheet = "https:" + datasheet

    # Fields shared by all tiers; name/value filled after generation
    common = {
        "name": "",
        "value": "",
        "reference": reference,
        "category": category,
        "subcategory": d.get("subcategory"),
        "package": d.get("package") or None,
        "mounting": d.get("mounting"),
        "description": d.get("description", ""),
        "tags": d.get("tags", []),
        "specifications": d.get("specifications"),
        "suppliers": suppliers,
        "symbol": d.get("symbol", ""),
        "footprint": d.get("footprint", ""),
        "keywords": d.get("keywords", []),
        "datasheet": datasheet,
        "notes": d.get("notes"),
    }

    part = _build_part(tier, d, common)

    # Use manual name if provided, otherwise auto-generate
    manual_name = d.get("name", "").strip()
    part.name = manual_name or generate_name(part, categories, separator)
    part.value = generate_value(part, categories)
    if isinstance(part, JellybeanPart):
        part.description = generate_description(part, categories)

    return part


def _build_part(
    tier: str,
    d: dict,
    common: dict,
) -> ProprietaryPart | SemiJellybeanPart | JellybeanPart:
    """Construct the tier-appropriate Part subclass from form data."""
    if tier == Tier.PROPRIETARY:
        mpn = d.get("mpn", "").strip()
        manufacturer = d.get("manufacturer", "").strip()
        if not mpn:
            raise ValidationNotice("MPN is required for proprietary parts")
        if not manufacturer:
            raise ValidationNotice("Manufacturer is required")
        return ProprietaryPart(
            tier=Tier.PROPRIETARY,
            mpn=mpn,
            manufacturer=manufacturer,
            **common,
        )

    if tier == Tier.SEMI_JELLYBEAN:
        mpn = d.get("mpn", "").strip()
        manufacturer = d.get("manufacturer", "").strip()
        base_pn = d.get("base_pn", "").strip()
        if not mpn:
            raise ValidationNotice("MPN is required")
        if not manufacturer:
            raise ValidationNotice("Manufacturer is required")
        if not base_pn:
            raise ValidationNotice("Base PN is required for semi-jellybean parts")
        return SemiJellybeanPart(
            tier=Tier.SEMI_JELLYBEAN,
            mpn=mpn,
            manufacturer=manufacturer,
            base_pn=base_pn,
            **common,
        )

    # Jellybean
    specs = d.get("specifications")
    if not specs:
        raise ValidationNotice("Specs are required for jellybean parts")
    common["specifications"] = specs
    return JellybeanPart(tier=Tier.JELLYBEAN, **common)
