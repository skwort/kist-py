"""Part data models -- tier-specific models and discriminated union."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Discriminator, Field, HttpUrl

Ipn = NewType("Ipn", str)


class Tier(StrEnum):
    PROPRIETARY = "proprietary"
    SEMI_JELLYBEAN = "semi-jellybean"
    JELLYBEAN = "jellybean"


class Mounting(StrEnum):
    SMD = "smd"
    THT = "tht"
    OTHER = "other"


class SupplierInfo(BaseModel):
    sku: str
    url: HttpUrl | None = None


class Alternate(BaseModel):
    mpn: str
    manufacturer: str
    notes: str | None = None
    suppliers: dict[str, SupplierInfo] = {}


class PartBase(BaseModel):
    """Common fields shared by all part tiers."""

    model_config = ConfigDict(extra="forbid")

    ipn: Ipn | None = Field(default=None, exclude=True)
    name: str
    description: str
    category: str
    subcategory: str | None = None
    package: str | None = None
    mounting: Mounting | None = None
    datasheet: HttpUrl | None = None
    tags: list[str] = []
    notes: str | None = None
    symbol: str
    footprint: str
    value: str
    reference: str
    keywords: list[str] = []
    specifications: dict[str, str] | None = None
    exclude_from_bom: bool = False
    exclude_from_board: bool = False
    footprint_variant: str | None = None
    suppliers: dict[str, SupplierInfo] = {}


class ProprietaryPart(PartBase):
    tier: Literal[Tier.PROPRIETARY]
    mpn: str
    manufacturer: str


class SemiJellybeanPart(PartBase):
    tier: Literal[Tier.SEMI_JELLYBEAN]
    base_pn: str
    mpn: str
    manufacturer: str
    alternates: list[Alternate] = []


class JellybeanPart(PartBase):
    tier: Literal[Tier.JELLYBEAN]
    alternates: list[Alternate] = []
    specifications: dict[str, str]


# A Part is one of the three tier-specific models, selected at validation time
# by the value of the ``tier`` field (Pydantic discriminated union).  Code that
# handles an arbitrary part uses this type; Pydantic resolves it to the correct
# concrete class on deserialisation.
Part = Annotated[
    ProprietaryPart | SemiJellybeanPart | JellybeanPart,
    Discriminator("tier"),
]
