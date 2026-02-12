"""
Category-to-library mapping per ADR-002 §4.

Maps each part category to a numbered KiCad library name, matching the
convention ``NNk-Name`` where NN is a two-digit sort prefix and ``k``
marks kist-managed libraries.
"""

from __future__ import annotations


def library_filename(
    category_name: str,
    library_prefix: str = "00k",
    separator: str = "-",
) -> str:
    """Return the ``.kicad_sym`` filename for a category name like ``"Resistors"``."""
    return f"{library_prefix}{separator}{category_name}.kicad_sym"


def symbol_reference(
    category_name: str,
    part_name: str,
    library_prefix: str = "00k",
    separator: str = "-",
) -> str:
    """
    Return a full KiCad symbol reference like ``00k-Resistors:RES-10K-1PCT-0603``.
    """
    return f"{library_prefix}{separator}{category_name}:{part_name}"
