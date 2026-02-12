"""Tests for category-to-library mapping."""

from __future__ import annotations

from kist.kicad.mapping import library_filename, symbol_reference


def test_library_filename_returns_kicad_sym():
    assert library_filename("Resistors") == "00k-Resistors.kicad_sym"
    assert library_filename("ICs") == "00k-ICs.kicad_sym"
    assert library_filename("Miscellaneous") == "00k-Miscellaneous.kicad_sym"


def test_library_filename_custom_prefix():
    assert (
        library_filename("Resistors", library_prefix="99k") == "99k-Resistors.kicad_sym"
    )


def test_library_filename_custom_separator():
    assert library_filename("Resistors", separator="_") == "00k_Resistors.kicad_sym"


def test_symbol_reference_format():
    ref = symbol_reference("Resistors", "RES-10K-1PCT-0603")
    assert ref == "00k-Resistors:RES-10K-1PCT-0603"


def test_symbol_reference_with_ic():
    ref = symbol_reference("ICs", "IC-STM32F405RGT6-LQFP64")
    assert ref == "00k-ICs:IC-STM32F405RGT6-LQFP64"
