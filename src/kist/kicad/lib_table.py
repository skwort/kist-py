"""
KiCad lib table generation and update.

Produces ``sym-lib-table`` (and eventually ``fp-lib-table``) files
using the S-expression format KiCad expects. Kist-managed entries
are identified by the library prefix + separator (e.g. ``00k-``).
"""

from __future__ import annotations

from pathlib import Path

from kist.sexpr import Atom, dumps, parse_one

# -- Constants ---

_VERSION = "7"


# -- Entry construction ---


def _lib_entry(name: str, uri: str) -> list:
    """
    Build a single ``(lib ...)`` S-expression node.
    """
    return [
        Atom("lib"),
        [Atom("name"), Atom(name, quoted=True)],
        [Atom("type"), Atom("KiCad", quoted=True)],
        [Atom("uri"), Atom(uri, quoted=True)],
        [Atom("options"), Atom("", quoted=True)],
        [Atom("descr"), Atom("", quoted=True)],
    ]


def _is_kist_entry(node: list, prefix: str, separator: str) -> bool:
    """True if this ``(lib ...)`` node is kist-managed."""
    if not node or node[0] != "lib":
        return False
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == "name" and len(child) > 1:
            return str(child[1]).startswith(f"{prefix}{separator}")
    return False


# -- Generation ---


def generate_sym_lib_table(
    symbol_files: list[Path],
    symbols_dir: str,
    library_prefix: str,
    separator: str,
) -> str:
    """
    Generate sym-lib-table content for kist-managed symbol libraries.

    *symbol_files* are ``.kicad_sym`` paths (only the stem is used).
    *symbols_dir* is the relative directory name (e.g. ``"symbols"``).
    URIs use ``${KIPRJMOD}/lib/<symbols_dir>/<filename>``.

    Returns the S-expression string ready to write to disk.
    """
    entries = []
    for path in sorted(symbol_files):
        name = path.stem
        uri = f"${{KIPRJMOD}}/lib/{symbols_dir}/{path.name}"
        entries.append(_lib_entry(name, uri))

    tree: list = [
        Atom("sym_lib_table"),
        [Atom("version"), Atom(_VERSION)],
        *entries,
    ]
    return dumps(tree)


# -- Update (merge) ---


def update_sym_lib_table(
    existing_content: str,
    symbol_files: list[Path],
    symbols_dir: str,
    library_prefix: str,
    separator: str,
) -> str:
    """
    Merge kist entries into an existing sym-lib-table.

    Removes all kist-managed ``(lib ...)`` entries (identified by
    *library_prefix* + *separator*), appends fresh entries for
    *symbol_files*, and preserves everything else.
    """
    tree = parse_one(existing_content)
    if not isinstance(tree, list) or not tree or tree[0] != "sym_lib_table":
        msg = f"Expected (sym_lib_table ...), got {tree[0]!r}"
        raise ValueError(msg)

    # Remove existing kist entries
    tree[:] = [
        node
        for node in tree
        if not (
            isinstance(node, list) and _is_kist_entry(node, library_prefix, separator)
        )
    ]

    # Append new kist entries
    for path in sorted(symbol_files):
        name = path.stem
        uri = f"${{KIPRJMOD}}/lib/{symbols_dir}/{path.name}"
        tree.append(_lib_entry(name, uri))

    return dumps(tree)
