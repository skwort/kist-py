"""Shared test fixtures for part factories and database setup."""

from pathlib import Path

import pytest
from pydantic import HttpUrl

from kist.core.database import PartsDatabase, create_empty
from kist.models import (
    Alternate,
    JellybeanPart,
    Mounting,
    ProprietaryPart,
    SemiJellybeanPart,
    SupplierInfo,
    Tier,
)


@pytest.fixture
def proprietary_part() -> ProprietaryPart:
    return ProprietaryPart(
        name="IC-STM32F405RGT6",
        tier=Tier.PROPRIETARY,
        description="ARM Cortex-M4 MCU, 1MB Flash, 168MHz",
        category="IC",
        subcategory="MCU",
        package="LQFP-64",
        mounting=Mounting.SMD,
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        symbol="MCU_ST_STM32F4:STM32F405RGTx",
        footprint="Package_QFP:LQFP-64_10x10mm_P0.5mm",
        value="STM32F405RGT6",
        reference="U",
        tags=["arm", "cortex-m4"],
    )


@pytest.fixture
def semi_jellybean_part() -> SemiJellybeanPart:
    return SemiJellybeanPart(
        name="IC-TL072",
        tier=Tier.SEMI_JELLYBEAN,
        description="Dual JFET-input operational amplifier",
        category="IC",
        subcategory="OPAMP",
        package="SO-8",
        mounting=Mounting.SMD,
        base_pn="TL072",
        mpn="TL072CDR",
        manufacturer="Texas Instruments",
        symbol="Amplifier_Operational:TL072",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        value="TL072",
        reference="U",
        alternates=[
            Alternate(mpn="TL072ACD", manufacturer="STMicroelectronics"),
            Alternate(mpn="TL072BCD", manufacturer="Onsemi"),
        ],
    )


@pytest.fixture
def jellybean_part() -> JellybeanPart:
    return JellybeanPart(
        name="RES-10K-1PCT-0603",
        tier=Tier.JELLYBEAN,
        description="10kΩ 1% 0603 resistors",
        category="RES",
        package="0603",
        mounting=Mounting.SMD,
        symbol="00k-Resistors:RES-10K-1PCT-0603",
        footprint="Resistor_SMD:R_0603_1608Metric",
        value="10K",
        reference="R",
        specifications={"resistance": "10kΩ", "tolerance": "1%"},
        alternates=[
            Alternate(
                mpn="RC0603FR-0710KL",
                manufacturer="Yageo",
                suppliers={
                    "digikey": SupplierInfo(
                        sku="311-10.0KHRCT-ND",
                        url=HttpUrl(
                            "https://www.digikey.com/en/products/detail/example"
                        ),
                    )
                },
            )
        ],
        tags=["basic"],
    )


@pytest.fixture
def db(tmp_path: Path) -> PartsDatabase:
    """An empty, loaded PartsDatabase backed by a temp file."""
    path = tmp_path / "parts.json"
    create_empty(path)
    database = PartsDatabase(path)
    database.load()
    return database
