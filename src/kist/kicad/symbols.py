"""
KiCad symbol library (.kicad_sym) read/write.

Wraps the generic S-expression layer with a domain-specific API for
listing, adding, replacing, and patching symbols inside a library file.
"""

from __future__ import annotations

from pathlib import Path

from kist.sexpr import Atom, SexprError, dumps, find_all, parse_one

# -- Constants ---

_LIB_TAG = "kicad_symbol_lib"
# TODO: verify what the YYYYMMDD version value represents -- file format
# revision date?  Matches KiCad 9.0 fixtures for now.
_VERSION = "20241209"
_GENERATOR = "kist"
_GENERATOR_VERSION = "1.0"


# -- SymbolLibrary ---


class SymbolLibrary:
    """
    In-memory representation of a ``.kicad_sym`` symbol library.

    Symbols are stored as raw S-expression subtrees so callers can
    inspect or mutate them with the helpers in :mod:`kist.sexpr`.
    """

    def __init__(self, tree: list) -> None:
        self._tree = tree

    # -- Constructors ---

    @classmethod
    def load(cls, path: str | Path) -> SymbolLibrary:
        """Parse a ``.kicad_sym`` file and return a library instance."""
        text = Path(path).read_text(encoding="utf-8")
        tree = parse_one(text)
        if not isinstance(tree, list) or not tree or tree[0] != _LIB_TAG:
            raise SexprError(f"Expected top-level ({_LIB_TAG} ...), got {tree[0]!r}")
        return cls(tree)

    @classmethod
    def empty(cls) -> SymbolLibrary:
        """Return a fresh library with only version and generator metadata."""
        tree: list = [
            Atom(_LIB_TAG),
            [Atom("version"), Atom(_VERSION)],
            [Atom("generator"), Atom(_GENERATOR, quoted=True)],
            [Atom("generator_version"), Atom(_GENERATOR_VERSION, quoted=True)],
        ]
        return cls(tree)

    # -- Persistence ---

    def save(self, path: str | Path) -> None:
        """Write the library to *path* with Unix line endings."""
        Path(path).write_text(dumps(self._tree), encoding="utf-8", newline="\n")

    # -- Symbol access ---

    def symbols(self) -> list[str]:
        """Return the names of all top-level symbols in definition order."""
        return [str(sym[1]) for sym in find_all(self._tree, "symbol") if len(sym) > 1]

    def get_symbol(self, name: str) -> list | None:
        """Return the S-expression subtree for *name*, or ``None``."""
        for sym in find_all(self._tree, "symbol"):
            if len(sym) > 1 and sym[1] == name:
                return sym
        return None

    def set_symbol(self, name: str, sexpr: list) -> None:
        """Add or replace the symbol called *name*."""
        for i, child in enumerate(self._tree):
            if (
                isinstance(child, list)
                and child
                and child[0] == "symbol"
                and len(child) > 1
                and child[1] == name
            ):
                self._tree[i] = sexpr
                return
        self._tree.append(sexpr)

    def remove_symbol(self, name: str) -> bool:
        """Remove the symbol called *name*.  Returns whether it existed."""
        for i, child in enumerate(self._tree):
            if (
                isinstance(child, list)
                and child
                and child[0] == "symbol"
                and len(child) > 1
                and child[1] == name
            ):
                del self._tree[i]
                return True
        return False

    # -- Property patching ---

    def update_properties(self, name: str, props: dict[str, str]) -> None:
        """
        Patch property values on the symbol called *name*.

        For each key in *props*, find the ``(property "Key" "Value" ...)``
        child and replace the value atom (index 2).  If the property
        doesn't exist, append a new minimal property node.

        Raises ``KeyError`` if the symbol doesn't exist.
        """
        sym = self.get_symbol(name)
        if sym is None:
            raise KeyError(name)

        for key, value in props.items():
            prop = None
            for child in sym:
                if (
                    isinstance(child, list)
                    and child
                    and child[0] == "property"
                    and len(child) > 2
                    and child[1] == key
                ):
                    prop = child
                    break

            if prop is not None:
                # Patch value in-place, preserving (at ...), (effects ...) etc.
                prop[2] = Atom(value, quoted=True)
            else:
                # Append a new minimal property
                sym.append(
                    [
                        Atom("property"),
                        Atom(key, quoted=True),
                        Atom(value, quoted=True),
                        [Atom("at"), Atom("0"), Atom("0"), Atom("0")],
                        [
                            Atom("effects"),
                            [Atom("font"), [Atom("size"), Atom("1.27"), Atom("1.27")]],
                            [Atom("hide"), Atom("yes")],
                        ],
                    ]
                )
