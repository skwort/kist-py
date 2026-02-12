"""
Category-to-library mapping per ADR-002 §4.

Maps each part category to a numbered KiCad library name, matching the
convention ``NNk-Name`` where NN is a two-digit sort prefix and ``k``
marks kist-managed libraries.
"""

from __future__ import annotations

from kist.models import Category

# -- Category-to-library mapping ---

CATEGORY_LIBRARY: dict[Category, str] = {
    Category.RES: "00k-Resistors",
    Category.CAP: "01k-Capacitors",
    Category.IND: "02k-Inductors",
    Category.DIO: "03k-Diodes",
    Category.TRAN: "04k-Transistors",
    Category.IC: "05k-ICs",
    Category.CONN: "06k-Connectors",
    Category.SW: "07k-Switches",
    Category.REL: "08k-Relays",
    Category.XTAL: "09k-Crystals",
    Category.FUSE: "10k-Fuses",
    Category.TFRM: "11k-Transformers",
    Category.TP: "12k-TestPoints",
    Category.FID: "13k-Fiducials",
    Category.MECH: "14k-Mechanical",
    Category.MISC: "15k-Misc",
}


def library_filename(category: Category) -> str:
    """Return the ``.kicad_sym`` filename for *category*."""
    return f"{CATEGORY_LIBRARY[category]}.kicad_sym"


def symbol_reference(category: Category, part_name: str) -> str:
    """
    Return a full KiCad symbol reference like ``00k-Resistors:RES-10K-1PCT-0603``.
    """
    return f"{CATEGORY_LIBRARY[category]}:{part_name}"
