"""Tests for the naming engine -- value normalisation, name generation, identity."""

from typing import Any

import pytest

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.naming import (
    generate_description,
    generate_name,
    generate_value,
    get_identity,
    normalise_capacitance,
    normalise_current,
    normalise_frequency,
    normalise_impedance,
    normalise_inductance,
    normalise_package,
    normalise_percentage,
    normalise_power,
    normalise_resistance,
    normalise_voltage,
)
from kist.models import (
    JellybeanPart,
    Mounting,
    ProprietaryPart,
    SemiJellybeanPart,
    Tier,
)

CATS = WELL_KNOWN_CATEGORIES

# -- normalise_resistance ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("10kΩ", "10K"),
        ("4.7kΩ", "4K7"),
        ("100Ω", "100R"),
        ("1MΩ", "1M"),
        ("4R7", "4R7"),
        ("10k", "10K"),
        ("4.7k", "4K7"),
        ("2.2kΩ", "2K2"),
        ("47Ω", "47R"),
        ("0.47Ω", "0R47"),
        ("1Ω", "1R"),
        ("10Ω", "10R"),
        ("100kΩ", "100K"),
        ("2.2MΩ", "2M2"),
        # DigiKey word-form units
        ("10 kOhms", "10K"),
        ("4.7 kOhms", "4K7"),
        ("374 Ohms", "374R"),
        ("5.1 kOhms", "5K1"),
        ("1 MOhms", "1M"),
        ("5 mOhms", "0R005"),
    ],
)
def test_normalise_resistance(input_val, expected):
    assert normalise_resistance(input_val) == expected


# -- normalise_capacitance ---------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("0.1µF", "100n"),
        ("100nF", "100n"),
        ("4.7µF", "4u7"),
        ("10pF", "10p"),
        ("100n", "100n"),
        ("1µF", "1u"),
        ("10µF", "10u"),
        ("22pF", "22p"),
        ("2.2nF", "2n2"),
        ("100µF", "100u"),
        ("1nF", "1n"),
        ("470pF", "470p"),
        ("4u7", "4u7"),
        # DigiKey space-separated format
        ("0.1 µF", "100n"),
        ("100 pF", "100p"),
        ("10000 pF", "10n"),
        # Sub-picofarad values
        ("0.7 pF", "0p7"),
    ],
)
def test_normalise_capacitance(input_val, expected):
    assert normalise_capacitance(input_val) == expected


# -- normalise_inductance ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("10µH", "10u"),
        ("4.7µH", "4u7"),
        ("100nH", "100n"),
        ("1µH", "1u"),
        ("2.2µH", "2u2"),
        ("100µH", "100u"),
        ("22nH", "22n"),
        ("330nH", "330n"),
    ],
)
def test_normalise_inductance(input_val, expected):
    assert normalise_inductance(input_val) == expected


# -- normalise_voltage -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("3.3V", "3V3"),
        ("50V", "50V"),
        ("1.8V", "1V8"),
        ("5V", "5V"),
        ("12V", "12V"),
        ("25V", "25V"),
        ("100V", "100V"),
        ("16V", "16V"),
        ("30V", "30V"),
        ("40V", "40V"),
        ("63V", "63V"),
        # DigiKey formats with qualifiers
        ("48VDC", "48V"),
        ("3.6V (Max)", "3V6"),
        ("5V (Max)", "5V"),
    ],
)
def test_normalise_voltage(input_val, expected):
    assert normalise_voltage(input_val) == expected


# -- normalise_current -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("1A", "1A"),
        ("1.2A", "1200mA"),
        ("500mA", "500mA"),
        ("5.8A", "5800mA"),
        ("2A", "2A"),
        ("3A", "3A"),
        ("200mA", "200mA"),
        ("20mA", "20mA"),
        # DigiKey space-separated formats
        ("3.42 A", "3420mA"),
        ("250 mA", "250mA"),
        ("540 mA", "540mA"),
    ],
)
def test_normalise_current(input_val, expected):
    assert normalise_current(input_val) == expected


# -- normalise_power ---------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("500mW", "500mW"),
        ("400W", "400W"),
        ("1W", "1W"),
        ("250mW", "250mW"),
        ("62.5mW", "62mW"),
    ],
)
def test_normalise_power(input_val, expected):
    assert normalise_power(input_val) == expected


# -- normalise_frequency -----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("8MHz", "8MHz"),
        ("16MHz", "16MHz"),
        ("32.768kHz", "32K768Hz"),
        ("100MHz", "100MHz"),
        ("1GHz", "1GHz"),
        ("48MHz", "48MHz"),
        # DigiKey space-separated
        ("32.768 kHz", "32K768Hz"),
    ],
)
def test_normalise_frequency(input_val, expected):
    assert normalise_frequency(input_val) == expected


# -- normalise_percentage ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("1%", "1PCT"),
        ("5%", "5PCT"),
        ("20%", "20PCT"),
        ("±10%", "10PCT"),
        ("0.1%", "0.1PCT"),
        # Non-numeric values are not real percentages
        ("Jumper", ""),
    ],
)
def test_normalise_percentage(input_val, expected):
    assert normalise_percentage(input_val) == expected


# -- normalise_impedance -----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("600Ω", "600R"),
        ("2200Ω", "2200R"),
        ("1kΩ", "1000R"),
        ("100Ω", "100R"),
    ],
)
def test_normalise_impedance(input_val, expected):
    assert normalise_impedance(input_val) == expected


# -- normalise_package -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("SOIC-8", "SO8"),
        ("SO-8", "SO8"),
        ("LQFP-64", "LQFP64"),
        ("0603", "0603"),
        ("SOT-23", "SOT23"),
        ("SOT-23-5", "SOT235"),
        ("SOT-23-6", "SOT236"),
        ("QFN-32", "QFN32"),
        ("TSSOP-16", "TSSOP16"),
        ("MSOP-8", "MSOP8"),
        ("SOT-223", "SOT223"),
        # Unknown packages: uppercase, strip alpha-digit hyphens
        ("SMA", "SMA"),
        ("SOD-323", "SOD323"),
        ("HC-49", "HC49"),
        ("10x10", "10X10"),
        # DigiKey parenthetical metric equivalents
        ("0402 (1005 Metric)", "0402"),
        ("0603 (1608 Metric)", "0603"),
        ("0805 (2012 Metric)", "0805"),
        ('16-TSSOP (0.173", 4.40mm Width)', "16-TSSOP"),
        ("SOT-23-6 (some note)", "SOT236"),
    ],
)
def test_normalise_package(input_val, expected):
    assert normalise_package(input_val) == expected


# -- Test-local part factories -----------------------------------------------

_COMMON_FIELDS = {
    "symbol": "test:test",
    "footprint": "test:test",
    "value": "test",
    "name": "placeholder",
    "description": "placeholder",
}


def _proprietary_stm32(**overrides: Any) -> ProprietaryPart:
    fields = {
        **_COMMON_FIELDS,
        "tier": Tier.PROPRIETARY,
        "category": "IC",
        "subcategory": "MCU",
        "package": "LQFP-64",
        "mounting": Mounting.SMD,
        "mpn": "STM32F405RGT6",
        "manufacturer": "STMicroelectronics",
        "reference": "U",
        **overrides,
    }
    return ProprietaryPart(**fields)  # type: ignore[arg-type]


def _semi_tl072(**overrides: Any) -> SemiJellybeanPart:
    fields = {
        **_COMMON_FIELDS,
        "tier": Tier.SEMI_JELLYBEAN,
        "category": "IC",
        "subcategory": "OPAMP",
        "package": "SO-8",
        "mounting": Mounting.SMD,
        "base_pn": "TL072",
        "mpn": "TL072CDR",
        "manufacturer": "Texas Instruments",
        "reference": "U",
        **overrides,
    }
    return SemiJellybeanPart(**fields)  # type: ignore[arg-type]


def _jellybean(
    category: str,
    subcategory: str | None,
    package: str,
    specs: dict[str, str],
    reference: str = "R",
    **overrides: Any,
) -> JellybeanPart:
    fields = {
        **_COMMON_FIELDS,
        "tier": Tier.JELLYBEAN,
        "category": category,
        "subcategory": subcategory,
        "package": package,
        "mounting": Mounting.SMD,
        "specifications": specs,
        "reference": reference,
        **overrides,
    }
    return JellybeanPart(**fields)  # type: ignore[arg-type]


# -- generate_name -----------------------------------------------------------


@pytest.mark.parametrize(
    "part, expected",
    [
        # Proprietary
        (_proprietary_stm32(), "IC-STM32F405RGT6-LQFP64"),
        # Semi-jellybean
        (_semi_tl072(), "IC-TL072-SO8"),
        # Jellybean -- passives
        (
            _jellybean(
                "RES",
                None,
                "0603",
                {"resistance": "10kΩ", "tolerance": "1%"},
            ),
            "RES-10K-1PCT-0603",
        ),
        (
            _jellybean(
                "CAP",
                "CER",
                "0603",
                {"capacitance": "100nF", "voltage_rating": "50V", "dielectric": "X7R"},
                reference="C",
            ),
            "CAP-CER-100n-50V-X7R-0603",
        ),
        (
            _jellybean(
                "CAP",
                "ELEC",
                "10x10",
                {"capacitance": "100µF", "voltage_rating": "25V"},
                reference="C",
            ),
            "CAP-ELEC-100u-25V-10X10",
        ),
        (
            _jellybean(
                "IND",
                None,
                "0805",
                {"inductance": "10µH", "current_rating": "1.2A"},
                reference="L",
            ),
            "IND-10u-1200mA-0805",
        ),
        (
            _jellybean(
                "IND",
                "FERRITE",
                "0805",
                {"impedance_100mhz": "600Ω", "current_rating": "2A"},
                reference="L",
            ),
            "IND-FERRITE-600R-2A-0805",
        ),
        # Jellybean -- semiconductors
        (
            _jellybean(
                "DIO",
                "LED",
                "0603",
                {"colour": "red"},
                reference="D",
            ),
            "DIO-LED-RED-0603",
        ),
        (
            _jellybean(
                "DIO",
                "ZENER",
                "SOD-323",
                {"zener_voltage": "3.3V", "power_rating": "500mW"},
                reference="D",
            ),
            "DIO-ZENER-3V3-500mW-SOD323",
        ),
        (
            _jellybean(
                "DIO",
                "TVS",
                "SMA",
                {"standoff_voltage": "5V", "peak_power": "400W"},
                reference="D",
            ),
            "DIO-TVS-5V-400W-SMA",
        ),
        (
            _jellybean(
                "TRAN",
                "NMOS",
                "SOT-23",
                {"vds_max": "30V", "id_max": "5.8A"},
                reference="Q",
            ),
            "TRAN-NMOS-30V-5800mA-SOT23",
        ),
        (
            _jellybean(
                "TRAN",
                "NPN",
                "SOT-23",
                {"vceo": "40V", "ic_max": "200mA"},
                reference="Q",
            ),
            "TRAN-NPN-40V-200mA-SOT23",
        ),
        # Jellybean -- other
        (
            _jellybean(
                "XTAL",
                None,
                "HC-49",
                {"frequency": "8MHz", "load_capacitance": "18pF"},
                reference="Y",
            ),
            "XTAL-8MHz-18p-HC49",
        ),
        (
            _jellybean(
                "FUSE",
                None,
                "1206",
                {"current_rating": "1A", "voltage_rating": "63V"},
                reference="F",
            ),
            "FUSE-1A-63V-1206",
        ),
        (
            _jellybean(
                "FUSE",
                "PTC",
                "0805",
                {"hold_current": "500mA", "voltage_rating": "16V"},
                reference="F",
            ),
            "FUSE-PTC-500mA-16V-0805",
        ),
    ],
    ids=[
        "proprietary_stm32",
        "semi_tl072",
        "jelly_res_10k",
        "jelly_cap_cer",
        "jelly_cap_elec",
        "jelly_ind_plain",
        "jelly_ind_ferrite",
        "jelly_led_red",
        "jelly_zener",
        "jelly_tvs",
        "jelly_nmos",
        "jelly_npn",
        "jelly_xtal",
        "jelly_fuse",
        "jelly_fuse_ptc",
    ],
)
def test_generate_name(part, expected):
    assert generate_name(part, CATS) == expected


def test_generate_name_footprint_variant():
    part = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
        footprint_variant="HS",
    )
    assert generate_name(part, CATS) == "RES-10K-1PCT-0603-HS"


# -- generate_value ----------------------------------------------------------


def test_generate_value_resistor():
    part = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    assert generate_value(part, CATS) == "10K"


def test_generate_value_capacitor():
    part = _jellybean(
        "CAP",
        "CER",
        "0603",
        {"capacitance": "100nF", "voltage_rating": "50V", "dielectric": "X7R"},
        reference="C",
    )
    assert generate_value(part, CATS) == "100n"


def test_generate_value_inductor():
    part = _jellybean(
        "IND",
        None,
        "0805",
        {"inductance": "10µH", "current_rating": "1.2A"},
        reference="L",
    )
    assert generate_value(part, CATS) == "10u"


def test_generate_value_led():
    part = _jellybean(
        "DIO",
        "LED",
        "0603",
        {"colour": "red"},
        reference="D",
    )
    assert generate_value(part, CATS) == "RED"


def test_generate_value_crystal():
    part = _jellybean(
        "XTAL",
        None,
        "HC-49",
        {"frequency": "8MHz", "load_capacitance": "18pF"},
        reference="Y",
    )
    assert generate_value(part, CATS) == "8MHz"


def test_generate_value_diode_jellybean():
    """Non-LED jellybean diode: key specs joined with /."""
    part = _jellybean(
        "DIO",
        "SCHOTTKY",
        "SOD-123",
        {"reverse_voltage": "40V", "forward_current": "1A"},
        reference="D",
    )
    assert generate_value(part, CATS) == "40V/1A"


def test_generate_value_proprietary():
    assert generate_value(_proprietary_stm32(), CATS) == "STM32F405RGT6"


def test_generate_value_semi_jellybean():
    assert generate_value(_semi_tl072(), CATS) == "TL072"


# -- generate_description ----------------------------------------------------


def test_generate_description_resistor():
    part = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    desc = generate_description(part, CATS)
    assert "10kΩ" in desc
    assert "1%" in desc
    assert "0603" in desc
    assert "resistors" in desc


def test_generate_description_capacitor():
    part = _jellybean(
        "CAP",
        "CER",
        "0603",
        {"capacitance": "100nF", "voltage_rating": "50V", "dielectric": "X7R"},
        reference="C",
    )
    desc = generate_description(part, CATS)
    assert "100nF" in desc
    assert "ceramic" in desc
    assert "capacitors" in desc


def test_generate_description_proprietary_unchanged():
    part = _proprietary_stm32(description="ARM Cortex-M4 MCU")
    assert generate_description(part, CATS) == "ARM Cortex-M4 MCU"


def test_generate_description_semi_jellybean_unchanged():
    part = _semi_tl072(description="Dual JFET-input opamp")
    assert generate_description(part, CATS) == "Dual JFET-input opamp"


# -- get_identity ------------------------------------------------------------


def test_identity_same_specs():
    a = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    b = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    assert get_identity(a, CATS) == get_identity(b, CATS)


def test_identity_different_package():
    a = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    b = _jellybean(
        "RES",
        None,
        "0402",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    assert get_identity(a, CATS) != get_identity(b, CATS)


def test_identity_different_subcategory():
    a = _jellybean(
        "DIO",
        None,
        "SOD-123",
        {"reverse_voltage": "40V", "forward_current": "1A"},
        reference="D",
    )
    b = _jellybean(
        "DIO",
        "SCHOTTKY",
        "SOD-123",
        {"reverse_voltage": "40V", "forward_current": "1A"},
        reference="D",
    )
    assert get_identity(a, CATS) != get_identity(b, CATS)


def test_identity_footprint_variant():
    a = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    b = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
        footprint_variant="HS",
    )
    assert get_identity(a, CATS) != get_identity(b, CATS)


def test_identity_proprietary_uses_mpn():
    identity = get_identity(_proprietary_stm32(), CATS)
    assert "STM32F405RGT6" in identity
    assert "IC" in identity


def test_identity_semi_jellybean_uses_base_pn():
    identity = get_identity(_semi_tl072(), CATS)
    assert "TL072" in identity
    assert "IC" in identity


def test_identity_normalisation():
    """Different input formats for the same value resolve identically."""
    a = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10kΩ", "tolerance": "1%"},
    )
    b = _jellybean(
        "RES",
        None,
        "0603",
        {"resistance": "10k", "tolerance": "1%"},
    )
    assert get_identity(a, CATS) == get_identity(b, CATS)
