"""Naming engine for value normalisation, name generation, and identity."""

from __future__ import annotations

import re

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
