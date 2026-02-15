"""Naming engine for value normalisation, name generation, and identity."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from kist.models.part import (
    JellybeanPart,
    ProprietaryPart,
    SemiJellybeanPart,
)

if TYPE_CHECKING:
    from kist.models.config import CategoryDef
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

# Map word-form units to canonical symbols (case-insensitive lookup)
_UNIT_WORDS: dict[str, str] = {
    "ohms": "Ω",
    "ohm": "Ω",
    "farads": "F",
    "farad": "F",
    "henrys": "H",
    "henry": "H",
    "henries": "H",
    "volts": "V",
    "volt": "V",
    "amps": "A",
    "amp": "A",
    "amperes": "A",
    "watts": "W",
    "watt": "W",
    "hertz": "Hz",
    "hz": "Hz",
}

# Trailing qualifiers to strip before parsing: "(Max)", "per Contact", etc.
_QUALIFIER_RE = re.compile(r"\s*(?:\(.*?\)|per\s+.*)$", re.IGNORECASE)

# Parenthetical portion of package strings: "0402 (1005 Metric)"
_PKG_PAREN_RE = re.compile(r"\s*\(.*\)\s*$")

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

# Standard form: number, optional SI prefix, optional unit (symbol or word)
# e.g. "4.7k", "100nF", "3.3V", "500mA", "8MHz", "10 kOhms"
_UNITS_PATTERN = "|".join(re.escape(u) for u in _UNITS)
_UNIT_WORDS_PATTERN = "|".join(re.escape(w) for w in _UNIT_WORDS)
_STANDARD_RE = re.compile(
    r"^([0-9]*\.?[0-9]+)\s*([pnµumkKMG])?\s*("
    + _UNITS_PATTERN
    + "|"
    + _UNIT_WORDS_PATTERN
    + r")?$",
    re.IGNORECASE,
)

# Strip hyphens between alpha and digit portions of unknown packages
_PKG_HYPHEN_RE = re.compile(r"([A-Za-z])-(\d)")


# -- Internal helpers --------------------------------------------------------


def _parse_engineering(s: str) -> tuple[float, str]:
    """
    Parse an engineering value string into (numeric_value, unit).

    Handles SI prefixes, unicode symbols, word-form units (``Ohms``,
    ``kOhms``), and shorthand notation where the multiplier letter
    replaces the decimal point (e.g. ``4K7``).

    Strips trailing qualifiers like ``(Max)`` and ``per Contact`` before
    parsing, and normalises ``VDC`` to ``V``.

    Returns the numeric value as a float and the base unit as a string
    (empty string if no unit was detected).
    """
    s = s.strip()

    # Strip trailing qualifiers: "(Max)", "(AC/DC)", "per Contact"
    s = _QUALIFIER_RE.sub("", s).strip()

    # Normalise VDC to V
    if s.endswith("VDC"):
        s = s[:-3] + "V"

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

    # Try standard form: "4.7kΩ", "100nF", "10k", "3.3V", "10 kOhms"
    m = _STANDARD_RE.match(s)
    if m:
        num_str, prefix, unit_str = m.group(1), m.group(2), m.group(3)
        value = float(num_str)
        if prefix:
            value *= _SI_PREFIXES[prefix]
        # Resolve word-form units to canonical symbols
        unit = unit_str or ""
        if unit:
            unit = _UNIT_WORDS.get(unit.lower(), unit)
        return (value, unit)

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
    # Pick the largest tier that fits (default to smallest tier)
    chosen_mult = tiers[0][0]
    chosen_letter = tiers[0][1]
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
    try:
        value = float(s)
    except ValueError:
        # Non-numeric values like "Jumper" are not real percentages
        return ""
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

    Strips parenthetical metric equivalents first (e.g.
    ``"0402 (1005 Metric)"`` becomes ``"0402"``). Then checks known
    aliases, and falls back to uppercasing with alpha-digit hyphen
    stripping.

    Examples: ``"SOIC-8"`` --> ``"SO8"``, ``"0603"`` --> ``"0603"``,
    ``"0402 (1005 Metric)"`` --> ``"0402"``.
    """
    s = s.strip()

    # Strip parenthetical suffixes: "0402 (1005 Metric)", etc.
    s = _PKG_PAREN_RE.sub("", s).strip()

    upper = s.upper()

    # Try exact match in aliases (case-insensitive via upper key)
    for alias, canonical in _PACKAGE_ALIASES.items():
        if upper == alias.upper():
            return canonical

    # Unknown: uppercase, strip hyphens between alpha and digits
    result = _PKG_HYPHEN_RE.sub(r"\1\2", s)
    return result.upper()


# -- Spec normalisers -------------------------------------------------------

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


# -- Name generation ---------------------------------------------------------


def _normalise_spec(field: str, value: str) -> str:
    """Normalise a single spec value using the appropriate normaliser."""
    normaliser = SPEC_NORMALISERS.get(field)
    if normaliser:
        return normaliser(value)
    return value.upper()


def _get_key_specs(part: JellybeanPart, cat_def: CategoryDef) -> list[str]:
    """
    Look up key spec field names for a jellybean part.

    Tries subcategory override first, falls back to base key_specs.
    """
    if part.subcategory:
        fields = cat_def.subcategory_key_specs.get(part.subcategory)
        if fields is not None:
            return fields
    return cat_def.key_specs


def generate_name(
    part: Part,
    categories: dict[str, CategoryDef],
    separator: str = "-",
) -> str:
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
        segments = [part.category, part.mpn]

    elif isinstance(part, SemiJellybeanPart):
        segments = [part.category, part.base_pn]

    else:
        # Jellybean
        segments: list[str] = [part.category]
        if part.subcategory:
            segments.append(part.subcategory.upper())

        cat_def = categories.get(part.category)
        if cat_def:
            for field in _get_key_specs(part, cat_def):
                raw = part.specifications.get(field, "")
                if raw:
                    segments.append(_normalise_spec(field, raw))

    if pkg:
        segments.append(pkg)

    if part.footprint_variant:
        segments.append(part.footprint_variant.upper())

    return separator.join(segments)


# -- Value generation --------------------------------------------------------


def _get_value_field(
    part: JellybeanPart, cat_def: CategoryDef
) -> str | list[str] | None:
    """Look up value_field, checking subcategory overrides first."""
    if part.subcategory:
        override = cat_def.subcategory_value_field.get(part.subcategory)
        if override is not None:
            return override
    return cat_def.value_field


def generate_value(
    part: Part,
    categories: dict[str, CategoryDef],
) -> str:
    """
    Generate the schematic display value for a part.

    Looks up ``value_field`` from the category config, normalises
    the corresponding spec(s), and joins with ``value_field_separator``
    when multiple fields are specified.
    """
    if isinstance(part, ProprietaryPart):
        return part.mpn
    if isinstance(part, SemiJellybeanPart):
        return part.base_pn

    cat_def = categories.get(part.category)
    if not cat_def:
        return part.name

    value_field = _get_value_field(part, cat_def)
    if not value_field:
        return part.name

    specs = part.specifications
    sep = cat_def.value_field_separator

    if isinstance(value_field, str):
        raw = specs.get(value_field, "")
        if raw:
            return _normalise_spec(value_field, raw)
        return part.name

    # List of fields
    normalised = []
    for field in value_field:
        raw = specs.get(field, "")
        if raw:
            normalised.append(_normalise_spec(field, raw))
    if normalised:
        return sep.join(normalised)
    return part.name


# -- Description generation -------------------------------------------------


def generate_description(
    part: Part,
    categories: dict[str, CategoryDef],
) -> str:
    """
    Generate a human-readable description for a part.

    For jellybean parts, builds a description from raw spec values,
    package, subcategory name, and lowercase category name.
    For proprietary/semi-jellybean, returns the existing description.
    """
    if isinstance(part, (ProprietaryPart, SemiJellybeanPart)):
        return part.description

    cat_def = categories.get(part.category)
    specs = part.specifications
    pkg = part.package or ""

    # Collect raw spec values in key_specs order
    if cat_def:
        key_fields = _get_key_specs(part, cat_def)
        spec_parts = [specs.get(f, "") for f in key_fields]
        cat_name = cat_def.name.lower()
        subcat_name = ""
        if part.subcategory:
            subcat_name = cat_def.subcategory_names.get(part.subcategory, "").lower()
    else:
        spec_parts = []
        cat_name = part.category.lower()
        subcat_name = ""

    parts = [p for p in spec_parts if p] + [pkg]
    if subcat_name:
        parts.append(subcat_name)
    parts.append(cat_name)
    return " ".join(p for p in parts if p)


# -- Identity ---------------------------------------------------------------


def get_identity(
    part: Part,
    categories: dict[str, CategoryDef],
) -> tuple[str, ...]:
    """
    Return the identity tuple for deduplication.

    Two parts with the same identity tuple are considered the same part.
    Includes footprint_variant so that e.g. ``RES-10K-1PCT-0603`` and
    ``RES-10K-1PCT-0603-HS`` remain distinct.
    """
    variant = part.footprint_variant or ""
    pkg = normalise_package(part.package) if part.package else ""

    if isinstance(part, ProprietaryPart):
        return (part.category, part.mpn, pkg, variant)

    if isinstance(part, SemiJellybeanPart):
        return (part.category, part.base_pn, pkg, variant)

    # Jellybean: category + subcategory + normalised key specs + package
    subcat = (part.subcategory or "").upper()
    cat_def = categories.get(part.category)
    normalised_specs = []
    if cat_def:
        for field in _get_key_specs(part, cat_def):
            raw = part.specifications.get(field, "")
            if raw:
                normalised_specs.append(_normalise_spec(field, raw))
    return (part.category, subcat, *normalised_specs, pkg, variant)
