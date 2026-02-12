"""Naming engine for value normalisation, name generation, and identity."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from kist.models.part import (
    Category,
    JellybeanPart,
    ProprietaryPart,
    SemiJellybeanPart,
)

if TYPE_CHECKING:
    from kist.models.part import Part

_SI_PREFIXES: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "µ": 1e-6,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

_UNITS: list[str] = ["Hz", "Ω", "F", "H", "V", "A", "W"]

_RES_TIERS: list[tuple[float, str]] = [
    (1.0, "R"),
    (1e3, "K"),
    (1e6, "M"),
    (1e9, "G"),
]

_CAP_TIERS: list[tuple[float, str]] = [
    (1e-12, "p"),
    (1e-9, "n"),
    (1e-6, "u"),
    (1e-3, "m"),
]

_IND_TIERS: list[tuple[float, str]] = [
    (1e-9, "n"),
    (1e-6, "u"),
    (1e-3, "m"),
]

_PACKAGE_ALIASES: dict[str, str] = {
    "SOIC-8": "SO8",
    "SO-8": "SO8",
    "SOIC-14": "SO14",
    "SO-14": "SO14",
    "SOIC-16": "SO16",
    "SO-16": "SO16",
    "SOT-23": "SOT23",
    "SOT-23-3": "SOT23",
    "SOT-23-5": "SOT235",
    "SOT-23-6": "SOT236",
    "SOT-223": "SOT223",
    "LQFP-32": "LQFP32",
    "LQFP-48": "LQFP48",
    "LQFP-64": "LQFP64",
    "LQFP-100": "LQFP100",
    "QFN-16": "QFN16",
    "QFN-20": "QFN20",
    "QFN-24": "QFN24",
    "QFN-32": "QFN32",
    "QFN-48": "QFN48",
    "TSSOP-8": "TSSOP8",
    "TSSOP-14": "TSSOP14",
    "TSSOP-16": "TSSOP16",
    "TSSOP-20": "TSSOP20",
    "MSOP-8": "MSOP8",
    "MSOP-10": "MSOP10",
}

# Matches forms like "4K7", "4R7", "100n", "10u", "2M2"
_SHORTHAND_RE = re.compile(r"^(\d+)([RKMGnup])(\d+)?$")

# Standard form: optional number, optional SI prefix, optional unit
# e.g. "4.7k", "100nF", "3.3V", "500mA", "8MHz"
_UNITS_PATTERN = "|".join(re.escape(u) for u in _UNITS)
_STANDARD_RE = re.compile(
    r"^([0-9]*\.?[0-9]+)\s*([pnµumkKMG])?\s*(" + _UNITS_PATTERN + r")?$"
)

# Strip hyphens between alpha and digit portions of unknown packages
_PKG_HYPHEN_RE = re.compile(r"([A-Za-z])-(\d)")


# -- Internal helpers --------------------------------------------------------


def _parse_engineering(s: str) -> tuple[float, str]:
    """
    Parse an engineering value string into (numeric_value, unit).

    Handles SI prefixes, unicode symbols, and shorthand notation where
    the multiplier letter replaces the decimal point (e.g. ``4K7``).

    Returns the numeric value as a float and the base unit as a string
    (empty string if no unit was detected).
    """
    s = s.strip()

    # Try shorthand first: "4K7", "4R7", "100n", "2M2"
    m = _SHORTHAND_RE.match(s)
    if m:
        whole, letter, frac = m.group(1), m.group(2), m.group(3)
        if letter == "R":
            multiplier = 1.0
            unit = "Ω"
        elif letter in _SI_PREFIXES:
            multiplier = _SI_PREFIXES[letter]
            unit = ""
        else:
            multiplier = 1.0
            unit = ""

        if frac:
            value = (int(whole) + int(frac) / (10 ** len(frac))) * multiplier
        else:
            value = int(whole) * multiplier
        return (value, unit)

    # Try standard form: "4.7kΩ", "100nF", "10k", "3.3V"
    m = _STANDARD_RE.match(s)
    if m:
        num_str, prefix, unit_str = m.group(1), m.group(2), m.group(3)
        value = float(num_str)
        if prefix:
            value *= _SI_PREFIXES[prefix]
        return (value, unit_str or "")

    msg = f"Cannot parse engineering value: {s!r}"
    raise ValueError(msg)


def _format_eng_rlc(
    value: float,
    tiers: list[tuple[float, str]],
) -> str:
    """
    Format a float into engineering shorthand using a tier list.

    Each tier is ``(multiplier, letter)``. The largest tier whose
    multiplier is <= *value* is chosen. When the result has a fractional
    part the letter replaces the decimal point (``4700`` with ``K`` tier
    becomes ``"4K7"``).

    *tiers* must be sorted ascending by multiplier.
    """
    # Pick the largest tier that fits
    chosen_mult = 1.0
    chosen_letter = tiers[0][1]  # fallback to smallest tier
    for mult, letter in tiers:
        if value >= mult * 0.9999:  # tolerance for float comparison
            chosen_mult = mult
            chosen_letter = letter

    scaled = value / chosen_mult

    # Round to 6 decimal places -- enough to survive IEEE 754 noise
    # (e.g. 4.7k parses as 4699.999...) without preserving meaningless
    # precision beyond what component values ever need.
    scaled = round(scaled, 6)

    # Check if it's a clean integer
    if scaled == int(scaled):
        return f"{int(scaled)}{chosen_letter}"

    # Decimal-replaces-multiplier: 4.7 becomes "4{letter}7"
    int_part = int(scaled)
    frac_str = f"{scaled:.10f}".split(".")[1].rstrip("0")
    return f"{int_part}{chosen_letter}{frac_str}"


# -- Public normalisers (all str --> str) ------------------------------------


def normalise_resistance(s: str) -> str:
    """
    Normalise a resistance value to canonical name form.

    Uses uppercase multipliers (``K``, ``M``) because part names are
    all-uppercase. The ``R`` suffix denotes bare ohms.

    Examples: ``"4.7kΩ"`` --> ``"4K7"``, ``"100Ω"`` --> ``"100R"``.
    """
    value, _unit = _parse_engineering(s)
    return _format_eng_rlc(value, _RES_TIERS)


def normalise_capacitance(s: str) -> str:
    """
    Normalise a capacitance value to canonical name form.

    Uses lowercase multipliers (``n``, ``u``, ``p``) per KiCad convention.

    Examples: ``"0.1µF"`` --> ``"100n"``, ``"4.7µF"`` --> ``"4u7"``.
    """
    value, _unit = _parse_engineering(s)
    return _format_eng_rlc(value, _CAP_TIERS)


def normalise_inductance(s: str) -> str:
    """
    Normalise an inductance value to canonical name form.

    Examples: ``"10µH"`` --> ``"10u"``, ``"4.7µH"`` --> ``"4u7"``.
    """
    value, _unit = _parse_engineering(s)
    return _format_eng_rlc(value, _IND_TIERS)


def normalise_voltage(s: str) -> str:
    """
    Normalise a voltage using V-replaces-decimal convention.

    Whole voltages keep simple form (``"50V"``); fractional voltages use
    ``V`` as decimal replacement (``"3.3V"`` becomes ``"3V3"``).

    Examples: ``"3.3V"`` --> ``"3V3"``, ``"50V"`` --> ``"50V"``.
    """
    value, _unit = _parse_engineering(s)
    value = round(value, 6)

    if value == int(value):
        return f"{int(value)}V"

    int_part = int(value)
    frac_str = f"{value:.10f}".split(".")[1].rstrip("0")
    return f"{int_part}V{frac_str}"


def normalise_current(s: str) -> str:
    """
    Normalise a current value.

    Whole amps stay as amps (``"1A"``); fractional amps convert to
    milliamps (``"1.2A"`` becomes ``"1200mA"``). This avoids the
    ambiguity of ``1A2`` since ``A`` is a unit, not a multiplier.

    Examples: ``"1A"`` --> ``"1A"``, ``"500mA"`` --> ``"500mA"``.
    """
    value, _unit = _parse_engineering(s)
    value = round(value, 6)

    if value >= 1.0 and value == int(value):
        return f"{int(value)}A"

    # Convert to milliamps
    ma = round(value * 1000)
    return f"{ma}mA"


def normalise_power(s: str) -> str:
    """
    Normalise a power value.

    Examples: ``"500mW"`` --> ``"500mW"``, ``"400W"`` --> ``"400W"``.
    """
    value, _unit = _parse_engineering(s)
    value = round(value, 6)

    if value >= 1.0:
        if value == int(value):
            return f"{int(value)}W"
        # Fractional watts: express in mW
        mw = round(value * 1000)
        return f"{mw}mW"

    # Sub-watt: express in milliwatts
    mw = round(value * 1000)
    return f"{mw}mW"


def normalise_frequency(s: str) -> str:
    """
    Normalise a frequency value.

    Uses standard SI prefixes with Hz suffix. Fractional values use
    the multiplier-replaces-decimal convention.

    Examples: ``"8MHz"`` --> ``"8MHz"``, ``"32.768kHz"`` --> ``"32K768Hz"``.
    """
    value, _unit = _parse_engineering(s)
    value = round(value, 6)

    freq_tiers: list[tuple[float, str]] = [
        (1.0, ""),
        (1e3, "K"),
        (1e6, "M"),
        (1e9, "G"),
    ]

    chosen_mult = 1.0
    chosen_letter = ""
    for mult, letter in freq_tiers:
        if value >= mult * 0.9999:
            chosen_mult = mult
            chosen_letter = letter

    scaled = round(value / chosen_mult, 6)

    if scaled == int(scaled):
        return f"{int(scaled)}{chosen_letter}Hz"

    int_part = int(scaled)
    frac_str = f"{scaled:.10f}".split(".")[1].rstrip("0")
    return f"{int_part}{chosen_letter}{frac_str}Hz"


def normalise_percentage(s: str) -> str:
    """
    Normalise a percentage value with PCT suffix.

    Examples: ``"1%"`` --> ``"1PCT"``, ``"5%"`` --> ``"5PCT"``.
    """
    s = s.strip().rstrip("%").strip()
    # Handle ± prefix
    s = s.lstrip("±").strip()
    value = float(s)
    if value == int(value):
        return f"{int(value)}PCT"
    return f"{value}PCT"


def normalise_impedance(s: str) -> str:
    """
    Normalise an impedance value with R suffix for ohms.

    Always uses bare ohms with R suffix (no K/M scaling), since ferrite
    bead and common-mode choke impedance values are conventionally
    expressed in ohms.

    Examples: ``"600Ω"`` --> ``"600R"``, ``"2200Ω"`` --> ``"2200R"``.
    """
    value, _unit = _parse_engineering(s)
    value = round(value, 6)

    if value == int(value):
        return f"{int(value)}R"

    int_part = int(value)
    frac_str = f"{value:.10f}".split(".")[1].rstrip("0")
    return f"{int_part}R{frac_str}"


def normalise_package(s: str) -> str:
    """
    Normalise a package designation.

    Known aliases are looked up first. Unknown packages are uppercased
    with hyphens between alpha and digit portions stripped.

    Examples: ``"SOIC-8"`` --> ``"SO8"``, ``"0603"`` --> ``"0603"``.
    """
    s = s.strip()
    upper = s.upper()

    # Try exact match in aliases (case-insensitive via upper key)
    for alias, canonical in _PACKAGE_ALIASES.items():
        if upper == alias.upper():
            return canonical

    # Unknown: uppercase, strip hyphens between alpha and digits
    result = _PKG_HYPHEN_RE.sub(r"\1\2", s)
    return result.upper()


# -- Key specs and spec normalisers (ADR-001 §7) ----------------------------

KEY_SPECS: dict[tuple[Category, str | None], list[str]] = {
    (Category.RES, None): ["resistance", "tolerance"],
    (Category.CAP, "CER"): ["capacitance", "voltage_rating", "dielectric"],
    (Category.CAP, "ELEC"): ["capacitance", "voltage_rating"],
    (Category.CAP, "TANT"): ["capacitance", "voltage_rating"],
    (Category.CAP, "FILM"): ["capacitance", "voltage_rating"],
    (Category.IND, None): ["inductance", "current_rating"],
    (Category.IND, "FERRITE"): ["impedance_100mhz", "current_rating"],
    (Category.IND, "CM"): ["impedance", "current_rating"],
    (Category.IND, "CHOKE"): ["inductance", "current_rating"],
    (Category.DIO, None): ["reverse_voltage", "forward_current"],
    (Category.DIO, "SCHOTTKY"): ["reverse_voltage", "forward_current"],
    (Category.DIO, "ZENER"): ["zener_voltage", "power_rating"],
    (Category.DIO, "TVS"): ["standoff_voltage", "peak_power"],
    (Category.DIO, "LED"): ["colour"],
    (Category.TRAN, "NMOS"): ["vds_max", "id_max"],
    (Category.TRAN, "PMOS"): ["vds_max", "id_max"],
    (Category.TRAN, "NPN"): ["vceo", "ic_max"],
    (Category.TRAN, "PNP"): ["vceo", "ic_max"],
    (Category.FUSE, None): ["current_rating", "voltage_rating"],
    (Category.FUSE, "PTC"): ["hold_current", "voltage_rating"],
    (Category.XTAL, None): ["frequency", "load_capacitance"],
}

SPEC_NORMALISERS: dict[str, Callable[[str], str]] = {
    "resistance": normalise_resistance,
    "capacitance": normalise_capacitance,
    "inductance": normalise_inductance,
    "tolerance": normalise_percentage,
    "voltage_rating": normalise_voltage,
    "reverse_voltage": normalise_voltage,
    "zener_voltage": normalise_voltage,
    "standoff_voltage": normalise_voltage,
    "vds_max": normalise_voltage,
    "vceo": normalise_voltage,
    "forward_current": normalise_current,
    "current_rating": normalise_current,
    "id_max": normalise_current,
    "ic_max": normalise_current,
    "hold_current": normalise_current,
    "power_rating": normalise_power,
    "peak_power": normalise_power,
    "impedance_100mhz": normalise_impedance,
    "impedance": normalise_impedance,
    "frequency": normalise_frequency,
    "load_capacitance": normalise_capacitance,
    "dielectric": str.upper,
    "colour": str.upper,
}

# Lowercase-multiplier tiers for schematic display values (KiCad convention)
_VALUE_RES_TIERS: list[tuple[float, str]] = [
    (1.0, "R"),
    (1e3, "k"),
    (1e6, "M"),
    (1e9, "G"),
]

# Category names for human-readable descriptions
_CATEGORY_NAMES: dict[Category, str] = {
    Category.RES: "resistor",
    Category.CAP: "capacitor",
    Category.IND: "inductor",
    Category.DIO: "diode",
    Category.TRAN: "transistor",
    Category.XTAL: "crystal",
    Category.FUSE: "fuse",
}

_CAP_SUBCAT_NAMES: dict[str, str] = {
    "CER": "ceramic",
    "ELEC": "electrolytic",
    "TANT": "tantalum",
    "FILM": "film",
}


# -- Name generation (ADR-001 §2) -------------------------------------------


def _normalise_spec(field: str, value: str) -> str:
    """Normalise a single spec value using the appropriate normaliser."""
    normaliser = SPEC_NORMALISERS.get(field)
    if normaliser:
        return normaliser(value)
    return value.upper()


def _get_key_specs(part: JellybeanPart) -> list[str]:
    """
    Look up and return the key spec field names for a jellybean part.

    Falls back to (category, None) if the exact (category, subcategory)
    pair isn't registered.
    """
    key = (part.category, part.subcategory)
    fields = KEY_SPECS.get(key)
    if fields is None:
        fields = KEY_SPECS.get((part.category, None), [])
    return fields


def generate_name(part: Part) -> str:
    """
    Generate the canonical part name from structured fields.

    Dispatches by tier:
    - Proprietary: ``CATEGORY-MPN-PACKAGE``
    - Semi-jellybean: ``CATEGORY-BASE_PN-PACKAGE``
    - Jellybean: ``CATEGORY[-SUBCATEGORY]-SPECS-PACKAGE``

    Package is always last (before footprint variant). Appends
    ``-VARIANT`` if ``footprint_variant`` is set.
    """
    pkg = normalise_package(part.package) if part.package else ""

    if isinstance(part, ProprietaryPart):
        segments = [part.category.value, part.mpn]

    elif isinstance(part, SemiJellybeanPart):
        segments = [part.category.value, part.base_pn]

    else:
        # Jellybean
        segments = [part.category.value]
        if part.subcategory:
            segments.append(part.subcategory.upper())

        # Normalise key specs in order
        for field in _get_key_specs(part):
            raw = part.specifications.get(field, "")
            if raw:
                segments.append(_normalise_spec(field, raw))

    if pkg:
        segments.append(pkg)

    if part.footprint_variant:
        segments.append(part.footprint_variant.upper())

    return "-".join(segments)


# -- Value generation (ADR-001 §8) ------------------------------------------


def generate_value(part: Part) -> str:
    """
    Generate the schematic display value for a part.

    Passives use lowercase engineering shorthand (KiCad convention).
    Proprietary/semi-jellybean parts use their MPN or base_pn.
    """
    # Proprietary/semi-jellybean: use MPN or base_pn
    if isinstance(part, ProprietaryPart):
        return part.mpn
    if isinstance(part, SemiJellybeanPart):
        return part.base_pn

    # Jellybean -- dispatch by category
    specs = part.specifications

    if part.category == Category.RES:
        raw = specs.get("resistance", "")
        if raw:
            value, _unit = _parse_engineering(raw)
            return _format_eng_rlc(value, _VALUE_RES_TIERS)

    if part.category == Category.CAP:
        raw = specs.get("capacitance", "")
        if raw:
            return normalise_capacitance(raw)

    if part.category == Category.IND:
        raw = specs.get("inductance", "")
        if raw:
            return normalise_inductance(raw)

    if part.category == Category.DIO and part.subcategory == "LED":
        colour = specs.get("colour", "")
        if colour:
            return colour.upper()

    if part.category == Category.XTAL:
        raw = specs.get("frequency", "")
        if raw:
            return normalise_frequency(raw)

    # Jellybean diode (non-LED): key specs joined with /
    if part.category == Category.DIO:
        key_fields = _get_key_specs(part)
        normalised = []
        for field in key_fields:
            raw = specs.get(field, "")
            if raw:
                normalised.append(_normalise_spec(field, raw))
        if normalised:
            return "/".join(normalised)

    # Fallback
    return part.name


# -- Description generation -------------------------------------------------


def generate_description(part: Part) -> str:
    """
    Generate a human-readable description for a part.

    For jellybean parts, builds a description from specs and category.
    For proprietary/semi-jellybean, returns the existing description.
    """
    if isinstance(part, (ProprietaryPart, SemiJellybeanPart)):
        return part.description

    specs = part.specifications
    pkg = part.package or ""

    if part.category == Category.RES:
        resistance = specs.get("resistance", "")
        tolerance = specs.get("tolerance", "")
        parts = [resistance, tolerance, pkg, "thick film resistor"]
        return " ".join(p for p in parts if p)

    if part.category == Category.CAP:
        capacitance = specs.get("capacitance", "")
        voltage = specs.get("voltage_rating", "")
        dielectric = specs.get("dielectric", "")
        subcat_name = _CAP_SUBCAT_NAMES.get(part.subcategory or "", "")
        parts = [capacitance, voltage, dielectric, pkg]
        label = f"{subcat_name} capacitor" if subcat_name else "capacitor"
        return " ".join(p for p in parts if p) + " " + label

    # Generic jellybean: join all key spec values
    key_fields = _get_key_specs(part)
    spec_parts = [specs.get(f, "") for f in key_fields]
    cat_name = _CATEGORY_NAMES.get(part.category, part.category.value)
    parts = [p for p in spec_parts if p] + [pkg, cat_name]
    return " ".join(p for p in parts if p)


# -- Identity (ADR-001 §7) --------------------------------------------------


def get_identity(part: Part) -> tuple[str, ...]:
    """
    Return the identity tuple for deduplication.

    Two parts with the same identity tuple are considered the same part.
    Includes footprint_variant so that e.g. ``RES-10K-1PCT-0603`` and
    ``RES-10K-1PCT-0603-HS`` remain distinct.
    """
    variant = part.footprint_variant or ""
    pkg = normalise_package(part.package) if part.package else ""

    if isinstance(part, ProprietaryPart):
        return (part.category.value, part.mpn, pkg, variant)

    if isinstance(part, SemiJellybeanPart):
        return (part.category.value, part.base_pn, pkg, variant)

    # Jellybean: category + subcategory + normalised key specs + package
    subcat = (part.subcategory or "").upper()
    normalised_specs = []
    for field in _get_key_specs(part):
        raw = part.specifications.get(field, "")
        if raw:
            normalised_specs.append(_normalise_spec(field, raw))
    return (part.category.value, subcat, *normalised_specs, pkg, variant)
