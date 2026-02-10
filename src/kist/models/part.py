"""Part data models — enums, base models, and discriminated union."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, HttpUrl


class Tier(StrEnum):
    PROPRIETARY = "proprietary"
    SEMI_JELLYBEAN = "semi-jellybean"
    JELLYBEAN = "jellybean"


class Category(StrEnum):
    RES = "RES"
    CAP = "CAP"
    IND = "IND"
    DIO = "DIO"
    TRAN = "TRAN"
    IC = "IC"
    CONN = "CONN"
    SW = "SW"
    REL = "REL"
    XTAL = "XTAL"
    FUSE = "FUSE"
    TFRM = "TFRM"
    TP = "TP"
    FID = "FID"
    MECH = "MECH"
    MISC = "MISC"


class Mounting(StrEnum):
    SMD = "smd"
    THT = "tht"
    OTHER = "other"


class RefDes(StrEnum):
    """Reference designator prefixes per IEEE 315 / IEC 60617."""

    R = "R"
    C = "C"
    L = "L"
    D = "D"
    Q = "Q"
    U = "U"
    J = "J"
    SW = "SW"
    K = "K"
    Y = "Y"
    F = "F"
    T = "T"
    TP = "TP"
    FID = "FID"
    H = "H"
    FL = "FL"


CATEGORY_REFDES: dict[Category, RefDes] = {
    Category.RES: RefDes.R,
    Category.CAP: RefDes.C,
    Category.IND: RefDes.L,
    Category.DIO: RefDes.D,
    Category.TRAN: RefDes.Q,
    Category.IC: RefDes.U,
    Category.CONN: RefDes.J,
    Category.SW: RefDes.SW,
    Category.REL: RefDes.K,
    Category.XTAL: RefDes.Y,
    Category.FUSE: RefDes.F,
    Category.TFRM: RefDes.T,
    Category.TP: RefDes.TP,
    Category.FID: RefDes.FID,
    Category.MECH: RefDes.H,
    Category.MISC: RefDes.U,
}


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

    name: str
    description: str
    category: Category
    subcategory: str | None = None
    package: str | None = None
    mounting: Mounting | None = None
    datasheet: HttpUrl | None = None
    tags: list[str] = []
    notes: str | None = None
    symbol: str
    footprint: str
    value: str
    reference: RefDes
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


Part = Annotated[
    ProprietaryPart | SemiJellybeanPart | JellybeanPart,
    Discriminator("tier"),
]
