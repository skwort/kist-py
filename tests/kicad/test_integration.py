"""End-to-end integration test for the kist.kicad public API."""

from __future__ import annotations

from pathlib import Path

from kist.kicad import (
    SymbolLibrary,
    build_properties,
    library_filename,
    symbol_for_part,
    symbol_reference,
)
from kist.models import JellybeanPart, ProprietaryPart, SemiJellybeanPart
from kist.sexpr import find_all


def test_full_workflow(
    tmp_path: Path,
    jellybean_part: JellybeanPart,
    proprietary_part: ProprietaryPart,
    semi_jellybean_part: SemiJellybeanPart,
):
    """Create library, add symbols from fixtures, save, reload, verify."""
    lib = SymbolLibrary.empty()

    parts = [jellybean_part, proprietary_part, semi_jellybean_part]
    for part in parts:
        sym = symbol_for_part(part)
        lib.set_symbol(part.name, sym)

    # All symbols present before save
    assert lib.symbols() == [p.name for p in parts]

    # Save and reload
    out = tmp_path / "test.kicad_sym"
    lib.save(out)
    reloaded = SymbolLibrary.load(out)

    # All symbols survived round-trip
    assert reloaded.symbols() == [p.name for p in parts]

    # Properties correct on each symbol
    for part in parts:
        sym = reloaded.get_symbol(part.name)
        assert sym is not None

        props = build_properties(part)
        for child in sym:
            if (
                isinstance(child, list)
                and child
                and child[0] == "property"
                and len(child) > 2
                and child[1] == "Value"
            ):
                assert child[2] == props["Value"]
                break

    # Jellybean resistor has graphic sub-symbols with pins
    r_sym = reloaded.get_symbol(jellybean_part.name)
    assert r_sym is not None
    pin_count = sum(
        len(find_all(subsym, "pin")) for subsym in find_all(r_sym, "symbol")
    )
    assert pin_count == 2

    # Proprietary IC is a stub -- no pins
    ic_sym = reloaded.get_symbol(proprietary_part.name)
    assert ic_sym is not None
    ic_pin_count = sum(
        len(find_all(subsym, "pin")) for subsym in find_all(ic_sym, "symbol")
    )
    assert ic_pin_count == 0

    # symbol_reference produces correct lib:name strings
    for part in parts:
        ref = symbol_reference(part.category, part.name)
        filename = library_filename(part.category)
        assert ref.startswith(filename.removesuffix(".kicad_sym"))
        assert ref.endswith(f":{part.name}")
