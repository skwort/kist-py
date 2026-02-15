"""Tests for KiCad symbol templates."""

from __future__ import annotations

import pytest

from kist.core.categories import WELL_KNOWN_CATEGORIES
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

CATS = WELL_KNOWN_CATEGORIES

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
    assert props["Value"] == "10K"
    assert props["Footprint"] == "Resistor_SMD:R_0603_1608Metric"
    assert props["Datasheet"] == "~"  # no datasheet URL on fixture
    assert props["Description"] == "10kΩ 1% 0603 resistors"
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


# -- Helpers for property inspection ---


def _find_property(sym: list, key: str) -> list | None:
    """Find a (property "key" ...) child in a symbol tree."""
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == key
        ):
            return child
    return None


def _is_hidden(prop: list) -> bool:
    """True if property has (hide yes) in its effects."""
    for child in prop:
        if isinstance(child, list) and child and child[0] == "effects":
            for effect in child:
                if (
                    isinstance(effect, list)
                    and effect
                    and effect[0] == "hide"
                    and len(effect) > 1
                    and str(effect[1]) == "yes"
                ):
                    return True
    return False


# -- symbol_for_part dispatch ---


def test_symbol_for_part_resistor(jellybean_part: JellybeanPart):
    sym = symbol_for_part(jellybean_part, CATS)
    # Jellybean resistor gets full graphic template
    assert _count_pins(sym) == 2
    assert sym[1] == jellybean_part.name


def test_symbol_for_part_ic(proprietary_part: ProprietaryPart):
    sym = symbol_for_part(proprietary_part, CATS)
    # IC gets a stub -- no pins
    assert _count_pins(sym) == 0
    assert sym[1] == proprietary_part.name


# -- Spec properties ---


def test_symbol_for_part_includes_specs(jellybean_part: JellybeanPart):
    """Jellybean specs appear as properties on the generated symbol."""
    sym = symbol_for_part(jellybean_part, CATS)
    res_prop = _find_property(sym, "resistance")
    tol_prop = _find_property(sym, "tolerance")
    assert res_prop is not None
    assert str(res_prop[2]) == "10kΩ"
    assert tol_prop is not None
    assert str(tol_prop[2]) == "1%"


def test_spec_properties_hidden_by_default(jellybean_part: JellybeanPart):
    """Spec properties are hidden unless explicitly marked visible."""
    sym = symbol_for_part(jellybean_part, CATS)
    res_prop = _find_property(sym, "resistance")
    tol_prop = _find_property(sym, "tolerance")
    assert res_prop is not None and _is_hidden(res_prop)
    assert tol_prop is not None and _is_hidden(tol_prop)


def test_visible_specs_not_hidden(jellybean_part: JellybeanPart):
    """Specs in visible_specs set are not hidden."""
    sym = symbol_for_part(jellybean_part, CATS, visible_specs={"resistance"})
    res_prop = _find_property(sym, "resistance")
    tol_prop = _find_property(sym, "tolerance")
    assert res_prop is not None and not _is_hidden(res_prop)
    assert tol_prop is not None and _is_hidden(tol_prop)


def test_proprietary_part_no_spec_properties(proprietary_part: ProprietaryPart):
    """Proprietary parts without specs get no spec properties."""
    sym = symbol_for_part(proprietary_part, CATS)
    # Standard properties exist, but no spec properties
    assert _find_property(sym, "Reference") is not None
    assert _find_property(sym, "resistance") is None


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
