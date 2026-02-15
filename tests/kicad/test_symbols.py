"""Tests for SymbolLibrary read/write and symbol manipulation."""

from __future__ import annotations

from pathlib import Path

import pytest

from kist.kicad.symbols import SymbolLibrary, get_visible_properties
from kist.sexpr import Atom, dumps, find_one

FIXTURES = Path(__file__).parents[1] / "fixtures" / "kicad"
DEVICE_RCL = FIXTURES / "Device_RCL.kicad_sym"


# -- load ---


def test_load_device_rcl_symbols():
    lib = SymbolLibrary.load(DEVICE_RCL)
    names = lib.symbols()
    assert names == ["C", "L", "R"]


def test_load_rejects_wrong_tag(tmp_path):
    bad = tmp_path / "bad.kicad_sym"
    bad.write_text('(footprint "test")\n')
    with pytest.raises(Exception, match="kicad_symbol_lib"):
        SymbolLibrary.load(bad)


# -- save / round-trip ---


def test_load_save_reload_structural_equality(tmp_path):
    lib = SymbolLibrary.load(DEVICE_RCL)
    out = tmp_path / "out.kicad_sym"
    lib.save(out)

    reloaded = SymbolLibrary.load(out)
    assert reloaded.symbols() == lib.symbols()

    # Structural equality: same sexpr tree after round-trip
    for name in lib.symbols():
        orig_sym = lib.get_symbol(name)
        reload_sym = reloaded.get_symbol(name)
        assert orig_sym is not None
        assert reload_sym is not None
        assert dumps(reload_sym) == dumps(orig_sym)


# -- empty ---


def test_empty_round_trip(tmp_path):
    lib = SymbolLibrary.empty()
    assert lib.symbols() == []

    out = tmp_path / "empty.kicad_sym"
    lib.save(out)

    reloaded = SymbolLibrary.load(out)
    assert reloaded.symbols() == []


def test_empty_has_generator_metadata():
    lib = SymbolLibrary.empty()
    tree = lib._tree
    gen = find_one(tree, "generator")
    assert gen is not None
    assert gen[1] == "kist"


# -- set_symbol / get_symbol ---


def test_set_get_round_trip():
    lib = SymbolLibrary.empty()
    sym = [
        Atom("symbol"),
        Atom("MY_PART", quoted=True),
        [Atom("in_bom"), Atom("yes")],
    ]
    lib.set_symbol("MY_PART", sym)

    got = lib.get_symbol("MY_PART")
    assert got is not None
    assert got[1] == "MY_PART"
    assert lib.symbols() == ["MY_PART"]


def test_set_symbol_replaces_existing():
    lib = SymbolLibrary.empty()
    sym_v1 = [
        Atom("symbol"),
        Atom("X", quoted=True),
        [Atom("in_bom"), Atom("yes")],
    ]
    sym_v2 = [
        Atom("symbol"),
        Atom("X", quoted=True),
        [Atom("in_bom"), Atom("no")],
    ]
    lib.set_symbol("X", sym_v1)
    lib.set_symbol("X", sym_v2)

    assert lib.symbols() == ["X"]
    got = lib.get_symbol("X")
    assert got is not None
    bom = find_one(got, "in_bom")
    assert bom is not None
    assert bom[1] == "no"


def test_get_symbol_returns_none_for_missing():
    lib = SymbolLibrary.empty()
    assert lib.get_symbol("NOPE") is None


# -- remove_symbol ---


def test_remove_symbol_returns_true_and_removes():
    lib = SymbolLibrary.load(DEVICE_RCL)
    assert "R" in lib.symbols()
    assert lib.remove_symbol("R") is True
    assert "R" not in lib.symbols()


def test_remove_symbol_returns_false_for_missing():
    lib = SymbolLibrary.empty()
    assert lib.remove_symbol("NOPE") is False


# -- update_properties ---


def test_update_properties_patches_existing_value():
    lib = SymbolLibrary.load(DEVICE_RCL)
    lib.update_properties("R", {"Value": "10k"})

    sym = lib.get_symbol("R")
    assert sym is not None
    # Find the Value property
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == "Value"
        ):
            assert child[2] == "10k"
            # (at ...) and (effects ...) should still be present
            subtags = [c[0] for c in child if isinstance(c, list) and c]
            assert "at" in subtags
            assert "effects" in subtags
            break
    else:
        pytest.fail("Value property not found")


def test_update_properties_adds_new_property():
    lib = SymbolLibrary.load(DEVICE_RCL)
    lib.update_properties("R", {"MPN": "RC0603FR-0710KL"})

    sym = lib.get_symbol("R")
    assert sym is not None
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == "MPN"
        ):
            assert child[2] == "RC0603FR-0710KL"
            break
    else:
        pytest.fail("MPN property not found after update_properties")


# -- Round-trip patching (clean diff verification) ---


def test_patch_value_only_changes_one_line(tmp_path):
    """Load, patch a single property, save -- only the patched value differs."""
    original = SymbolLibrary.load(DEVICE_RCL)
    patched = SymbolLibrary.load(DEVICE_RCL)
    patched.update_properties("R", {"Value": "10k"})

    orig_out = tmp_path / "original.kicad_sym"
    patch_out = tmp_path / "patched.kicad_sym"
    original.save(orig_out)
    patched.save(patch_out)

    orig_lines = orig_out.read_text().splitlines()
    patch_lines = patch_out.read_text().splitlines()

    # Same number of lines -- structure unchanged
    assert len(orig_lines) == len(patch_lines)

    # Exactly one line differs
    diffs = [
        (i, o, p)
        for i, (o, p) in enumerate(zip(orig_lines, patch_lines, strict=True))
        if o != p
    ]
    assert len(diffs) == 1
    idx, old_line, new_line = diffs[0]
    assert '"R"' in old_line
    assert '"10k"' in new_line


def test_patch_preserves_unrelated_symbols(tmp_path):
    """Patching one symbol doesn't alter the serialised form of others."""
    original = SymbolLibrary.load(DEVICE_RCL)
    patched = SymbolLibrary.load(DEVICE_RCL)
    patched.update_properties("R", {"Value": "10k", "Description": "10k resistor"})

    for name in ["C", "L"]:
        orig_sym = original.get_symbol(name)
        patch_sym = patched.get_symbol(name)
        assert orig_sym is not None
        assert patch_sym is not None
        assert dumps(orig_sym) == dumps(patch_sym)


def test_patch_round_trips_through_file(tmp_path):
    """Patch, save, reload -- patched value persists, structure intact."""
    lib = SymbolLibrary.load(DEVICE_RCL)
    lib.update_properties("R", {"Value": "4.7k"})

    out = tmp_path / "patched.kicad_sym"
    lib.save(out)
    reloaded = SymbolLibrary.load(out)

    # Patched value persists
    sym = reloaded.get_symbol("R")
    assert sym is not None
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == "Value"
        ):
            assert child[2] == "4.7k"
            break
    else:
        pytest.fail("Value property not found after reload")

    # All symbols still present
    assert reloaded.symbols() == ["C", "L", "R"]

    # Save again -- output is byte-identical (stable serialisation)
    out2 = tmp_path / "patched2.kicad_sym"
    reloaded.save(out2)
    assert out.read_text() == out2.read_text()


def test_update_properties_raises_for_missing_symbol():
    lib = SymbolLibrary.empty()
    with pytest.raises(KeyError, match="NOPE"):
        lib.update_properties("NOPE", {"Value": "x"})


# -- get_visible_properties ---


def test_get_visible_properties_from_fixture():
    """Device_RCL symbols have Reference and Value visible."""
    lib = SymbolLibrary.load(DEVICE_RCL)
    sym = lib.get_symbol("R")
    assert sym is not None
    visible = get_visible_properties(sym)
    assert "Reference" in visible
    assert "Value" in visible
    # Hidden properties
    assert "Footprint" not in visible
    assert "Datasheet" not in visible


def test_get_visible_properties_all_hidden():
    """A symbol with only hidden properties returns empty set."""
    sym = [
        Atom("symbol"),
        Atom("X", quoted=True),
        [
            Atom("property"),
            Atom("Foo", quoted=True),
            Atom("bar", quoted=True),
            [Atom("at"), Atom("0"), Atom("0"), Atom("0")],
            [
                Atom("effects"),
                [Atom("font"), [Atom("size"), Atom("1.27"), Atom("1.27")]],
                [Atom("hide"), Atom("yes")],
            ],
        ],
    ]
    assert get_visible_properties(sym) == set()


def test_get_visible_properties_no_hide_means_visible():
    """A property without (hide yes) in effects is visible."""
    sym = [
        Atom("symbol"),
        Atom("X", quoted=True),
        [
            Atom("property"),
            Atom("MyField", quoted=True),
            Atom("val", quoted=True),
            [Atom("at"), Atom("0"), Atom("0"), Atom("0")],
            [
                Atom("effects"),
                [Atom("font"), [Atom("size"), Atom("1.27"), Atom("1.27")]],
            ],
        ],
    ]
    assert "MyField" in get_visible_properties(sym)


# -- Snapshot ---


def test_empty_with_symbol_snapshot(snapshot):
    lib = SymbolLibrary.empty()
    sym = [
        Atom("symbol"),
        Atom("TEST-PART", quoted=True),
        [Atom("in_bom"), Atom("yes")],
        [Atom("on_board"), Atom("yes")],
        [
            Atom("property"),
            Atom("Reference", quoted=True),
            Atom("R", quoted=True),
            [Atom("at"), Atom("0"), Atom("0"), Atom("0")],
        ],
        [
            Atom("property"),
            Atom("Value", quoted=True),
            Atom("10k", quoted=True),
            [Atom("at"), Atom("0"), Atom("0"), Atom("0")],
        ],
    ]
    lib.set_symbol("TEST-PART", sym)
    assert dumps(lib._tree) == snapshot
