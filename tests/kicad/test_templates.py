"""Tests for KiCad symbol templates."""

from __future__ import annotations

import pytest

from kist.kicad.templates import (
    build_properties,
    capacitor_symbol,
    inductor_symbol,
    resistor_symbol,
    stub_symbol,
    symbol_for_part,
)
from kist.models import JellybeanPart, ProprietaryPart
from kist.sexpr import dumps, find_all, parse_one

# -- Helpers ---


def _count_pins(sym: list) -> int:
    """Count pin nodes across all sub-symbols."""
    total = 0
    for subsym in find_all(sym, "symbol"):
        total += len(find_all(subsym, "pin"))
    return total


def _pin_types(sym: list) -> set[str]:
    """Collect pin electrical types from all sub-symbols."""
    types: set[str] = set()
    for subsym in find_all(sym, "symbol"):
        for pin in find_all(subsym, "pin"):
            if len(pin) > 1:
                types.add(str(pin[1]))
    return types


SAMPLE_PROPS = {
    "Reference": "R",
    "Value": "10k",
    "Footprint": "Resistor_SMD:R_0603_1608Metric",
    "Datasheet": "~",
    "Description": "10k resistor",
    "ki_keywords": "resistor",
}


# -- Round-trip (parseable output) ---


@pytest.mark.parametrize(
    "factory,name",
    [
        (resistor_symbol, "R-TEST"),
        (capacitor_symbol, "C-TEST"),
        (inductor_symbol, "L-TEST"),
        (stub_symbol, "U-TEST"),
    ],
)
def test_template_round_trips(factory, name):
    """Every template produces output that parses back identically."""
    sym = factory(name, SAMPLE_PROPS)
    text = dumps(sym)
    reparsed = parse_one(text)
    assert dumps(reparsed) == text


# -- Pin counts and types ---


def test_resistor_has_two_passive_pins():
    sym = resistor_symbol("R1", SAMPLE_PROPS)
    assert _count_pins(sym) == 2
    assert _pin_types(sym) == {"passive"}


def test_capacitor_has_two_passive_pins():
    sym = capacitor_symbol("C1", SAMPLE_PROPS)
    assert _count_pins(sym) == 2
    assert _pin_types(sym) == {"passive"}


def test_inductor_has_two_passive_pins():
    sym = inductor_symbol("L1", SAMPLE_PROPS)
    assert _count_pins(sym) == 2
    assert _pin_types(sym) == {"passive"}


def test_stub_has_no_pins():
    sym = stub_symbol("U1", SAMPLE_PROPS)
    assert _count_pins(sym) == 0


# -- build_properties ---


def test_build_properties_jellybean(jellybean_part: JellybeanPart):
    props = build_properties(jellybean_part)
    assert props["Reference"] == "R"
    assert props["Value"] == "10k"
    assert props["Footprint"] == "Resistor_SMD:R_0603_1608Metric"
    assert props["Datasheet"] == "~"  # no datasheet URL on fixture
    assert props["Description"] == "10kΩ 1% 0603 thick film resistor"
    assert "basic" in props["ki_keywords"]


def test_build_properties_proprietary(proprietary_part: ProprietaryPart):
    props = build_properties(proprietary_part)
    assert props["Reference"] == "U"
    assert props["Value"] == "STM32F405RGT6"
    assert "arm" in props["ki_keywords"]
    assert "cortex-m4" in props["ki_keywords"]


def test_build_properties_semi_jellybean(semi_jellybean_part):
    props = build_properties(semi_jellybean_part)
    assert props["Reference"] == "U"
    assert props["Value"] == "TL072"


# -- symbol_for_part dispatch ---


def test_symbol_for_part_resistor(jellybean_part: JellybeanPart):
    sym = symbol_for_part(jellybean_part)
    # Jellybean resistor gets full graphic template
    assert _count_pins(sym) == 2
    assert sym[1] == jellybean_part.name


def test_symbol_for_part_ic(proprietary_part: ProprietaryPart):
    sym = symbol_for_part(proprietary_part)
    # IC gets a stub -- no pins
    assert _count_pins(sym) == 0
    assert sym[1] == proprietary_part.name


# -- Snapshot tests ---


def test_resistor_snapshot(snapshot):
    sym = resistor_symbol("RES-10K", SAMPLE_PROPS)
    assert dumps(sym) == snapshot


def test_capacitor_snapshot(snapshot):
    props = {**SAMPLE_PROPS, "Reference": "C", "Value": "100n"}
    sym = capacitor_symbol("CAP-100N", props)
    assert dumps(sym) == snapshot


def test_inductor_snapshot(snapshot):
    props = {**SAMPLE_PROPS, "Reference": "L", "Value": "10u"}
    sym = inductor_symbol("IND-10U", props)
    assert dumps(sym) == snapshot


def test_stub_snapshot(snapshot):
    props = {**SAMPLE_PROPS, "Reference": "U", "Value": "STM32"}
    sym = stub_symbol("IC-STM32", props)
    assert dumps(sym) == snapshot
