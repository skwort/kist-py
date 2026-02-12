"""Tests for category-to-library mapping."""

from __future__ import annotations

from kist.kicad.mapping import CATEGORY_LIBRARY, library_filename, symbol_reference
from kist.models import Category


def test_category_library_covers_all_categories():
    """Every Category member has a mapping entry."""
    assert set(CATEGORY_LIBRARY.keys()) == set(Category)


def test_library_filename_returns_kicad_sym():
    assert library_filename(Category.RES) == "00k-Resistors.kicad_sym"
    assert library_filename(Category.IC) == "05k-ICs.kicad_sym"
    assert library_filename(Category.MISC) == "15k-Misc.kicad_sym"


def test_symbol_reference_format():
    ref = symbol_reference(Category.RES, "RES-10K-1PCT-0603")
    assert ref == "00k-Resistors:RES-10K-1PCT-0603"


def test_symbol_reference_with_ic():
    ref = symbol_reference(Category.IC, "IC-STM32F405RGT6-LQFP64")
    assert ref == "05k-ICs:IC-STM32F405RGT6-LQFP64"
