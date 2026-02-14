"""Tests for sym-lib-table generation and update."""

from pathlib import Path

from kist.kicad.lib_table import generate_sym_lib_table, update_sym_lib_table
from kist.sexpr import find_all, parse_one


def _parse_table(content: str) -> list:
    """Parse lib table content, asserting it's a list."""
    tree = parse_one(content)
    assert isinstance(tree, list)
    return tree


def _lib_names(content: str) -> list[str]:
    """Extract library names from a lib table string."""
    tree = _parse_table(content)
    names = []
    for lib in find_all(tree, "lib"):
        for child in lib[1:]:
            if isinstance(child, list) and child and child[0] == "name":
                names.append(str(child[1]))
    return names


def _lib_uris(content: str) -> list[str]:
    """Extract library URIs from a lib table string."""
    tree = _parse_table(content)
    uris = []
    for lib in find_all(tree, "lib"):
        for child in lib[1:]:
            if isinstance(child, list) and child and child[0] == "uri":
                uris.append(str(child[1]))
    return uris


# --- generate_sym_lib_table ---


def test_generate_empty_produces_valid_table():
    content = generate_sym_lib_table([], "symbols", "00k", "-")
    tree = _parse_table(content)
    assert tree[0] == "sym_lib_table"
    assert find_all(tree, "lib") == []


def test_generate_single_file():
    files = [Path("symbols/00k-Resistors.kicad_sym")]
    content = generate_sym_lib_table(files, "symbols", "00k", "-")

    names = _lib_names(content)
    assert names == ["00k-Resistors"]

    uris = _lib_uris(content)
    assert uris == ["${KIPRJMOD}/lib/symbols/00k-Resistors.kicad_sym"]


def test_generate_multiple_files_sorted():
    files = [
        Path("symbols/00k-ICs.kicad_sym"),
        Path("symbols/00k-Capacitors.kicad_sym"),
        Path("symbols/00k-Resistors.kicad_sym"),
    ]
    content = generate_sym_lib_table(files, "symbols", "00k", "-")

    names = _lib_names(content)
    assert names == ["00k-Capacitors", "00k-ICs", "00k-Resistors"]


def test_generate_custom_prefix_and_dir():
    files = [Path("sym/01k-Diodes.kicad_sym")]
    content = generate_sym_lib_table(files, "sym", "01k", "-")

    uris = _lib_uris(content)
    assert uris == ["${KIPRJMOD}/lib/sym/01k-Diodes.kicad_sym"]


def test_generate_roundtrip():
    """Generated content can be parsed back."""
    files = [
        Path("symbols/00k-Resistors.kicad_sym"),
        Path("symbols/00k-Capacitors.kicad_sym"),
    ]
    content = generate_sym_lib_table(files, "symbols", "00k", "-")
    tree = _parse_table(content)
    assert tree[0] == "sym_lib_table"
    assert len(find_all(tree, "lib")) == 2


# --- update_sym_lib_table ---


EXISTING_TABLE = """\
(sym_lib_table
  (version 7)
  (lib (name "power")(type "KiCad")(uri "${KICAD8_SYMBOL_DIR}/power.kicad_sym")(options "")(descr ""))
  (lib (name "00k-Resistors")(type "KiCad")(uri "${KIPRJMOD}/lib/symbols/00k-Resistors.kicad_sym")(options "")(descr ""))
)
"""


def test_update_replaces_kist_entries():
    new_files = [
        Path("symbols/00k-Capacitors.kicad_sym"),
        Path("symbols/00k-Resistors.kicad_sym"),
    ]
    content = update_sym_lib_table(EXISTING_TABLE, new_files, "symbols", "00k", "-")
    names = _lib_names(content)

    # Non-kist entry preserved
    assert "power" in names
    # Old kist entry replaced, new one added
    assert "00k-Resistors" in names
    assert "00k-Capacitors" in names


def test_update_preserves_non_kist_entries():
    content = update_sym_lib_table(EXISTING_TABLE, [], "symbols", "00k", "-")
    names = _lib_names(content)
    assert names == ["power"]


def test_update_kist_entries_appended_after_non_kist():
    new_files = [Path("symbols/00k-Diodes.kicad_sym")]
    content = update_sym_lib_table(EXISTING_TABLE, new_files, "symbols", "00k", "-")
    names = _lib_names(content)
    # power should still be first, kist entries after
    assert names[0] == "power"
    assert "00k-Diodes" in names


def test_update_different_prefix_leaves_entries_alone():
    """Entries with a different prefix are not touched."""
    new_files = [Path("symbols/01k-Resistors.kicad_sym")]
    content = update_sym_lib_table(EXISTING_TABLE, new_files, "symbols", "01k", "-")
    names = _lib_names(content)
    # 00k-Resistors is NOT kist-managed under prefix 01k, so it stays
    assert "00k-Resistors" in names
    assert "01k-Resistors" in names
    assert "power" in names
