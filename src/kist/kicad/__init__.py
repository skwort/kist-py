"""KiCad file handling -- symbol libraries, templates, and category mapping."""

from kist.kicad.mapping import library_filename, symbol_reference
from kist.kicad.symbols import SymbolLibrary
from kist.kicad.templates import (
    build_properties,
    capacitor_symbol,
    inductor_symbol,
    resistor_symbol,
    resistor_symbol_iec,
    stub_symbol,
    symbol_for_part,
)

__all__ = [
    "SymbolLibrary",
    "build_properties",
    "capacitor_symbol",
    "inductor_symbol",
    "library_filename",
    "resistor_symbol",
    "resistor_symbol_iec",
    "stub_symbol",
    "symbol_for_part",
    "symbol_reference",
]
