"""
Generic S-expression tokenizer, parser, and writer.

Handles the KiCad dialect and produces KiCad v8-style formatted output.
No kist imports -- this module is fully standalone.

KiCad S-expression format
-------------------------

KiCad stores schematics, symbols, footprints, and board files as
S-expressions -- nested parenthesised lists similar to Lisp.  A file
is a single top-level list whose first element is a tag keyword:

    (kicad_symbol_lib
        (version 20241209)
        (symbol "R"
            (property "Reference" "R" ...)
            ...))

There are three token types:

  **Keywords** -- bare unquoted identifiers and numbers.  Written as-is.
      ``version``, ``symbol``, ``20241209``, ``0.254``, ``yes``

  **Quoted strings** -- double-quoted, with backslash escapes
      (``\\"``, ``\\\\``, ``\\n``, ``\\r``).  Used for property names,
      values, paths, and any text containing whitespace or special chars.
      Empty strings and ``#``-prefixed strings are always quoted.
          ``"Reference"``, ``"R"``, ``""``, ``"#power"``

  **Lists** -- ``( ... )`` containing keywords, strings, and nested lists.
      The first element is conventionally a tag keyword that identifies
      the list type: ``(property ...)``, ``(symbol ...)``, ``(at x y)``.

Numbers are *not* parsed to int/float -- they stay as strings to avoid
float precision issues and preserve the exact text representation KiCad
wrote (e.g. ``1.0`` vs ``1``, trailing zeros).

Round-trip fidelity
~~~~~~~~~~~~~~~~~~~

The ``Atom`` type (a ``str`` subclass) records whether the source text
was quoted, so the writer reproduces KiCad's quoting choices.  Without
this, atoms like ``"R"`` that don't *need* quotes would be written bare,
producing noisy git diffs when KiCad re-saves the file with its own
quoting convention.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import NamedTuple

# -- Exceptions ---


class SexprError(Exception):
    """S-expression parse or serialisation error."""


# -- Data types ---


class Atom(str):
    """
    A single S-expression token that remembers its source quoting.

    Keywords are unquoted:  ``version``, ``yes``, ``0.254``
    Strings are quoted:     ``"Reference"``, ``"R"``, ``""``

    Behaves as a plain ``str`` for all operations.  The writer checks
    ``.quoted`` to decide whether to emit quotes, preserving the
    original file's conventions on round-trip.
    """

    quoted: bool

    def __new__(cls, value: str, *, quoted: bool = False) -> Atom:
        obj = super().__new__(cls, value)
        obj.quoted = quoted
        return obj

    def __repr__(self) -> str:
        return f"Atom({super().__repr__()}, quoted={self.quoted})"


# The recursive type: either an atom (str) or a tagged list.
# Lists use the first element as a tag keyword; remaining elements are
# children -- atoms or nested lists.
#     ["property", "Reference", "R", ["at", "0", "0", "0"]]
SExpr = str | list["SExpr"]


# -- Constants ---

# Backslash escape map for quoted strings
_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "r": "\r",
}

# Tags whose lists are collapsed to a single line regardless of child count
_SHORTFORM_TAGS = frozenset(
    {
        "font",
        "stroke",
        "fill",
        "offset",
        "rotate",
        "scale",
        "teardrop",
        "effects",
        "at",
        "size",
        "width",
        "type",
        "color",
        "xy",
        "start",
        "mid",
        "end",
        "center",
        "radius",
        "length",
        "number",
        "name",
    }
)

# Maximum column width before pts wraps
_PTS_MAX_COL = 99


# -- Tokenizer ---


class TokenKind(StrEnum):
    OPEN = "OPEN"  # (
    CLOSE = "CLOSE"  # )
    ATOM = "ATOM"  # unquoted keyword or number
    QSTRING = "QSTRING"  # quoted string with escapes resolved


class Token(NamedTuple):
    kind: TokenKind
    value: str
    offset: int


def tokenize(text: str) -> Iterator[Token]:
    """
    Yield tokens from an S-expression string.

    Token kinds: ``OPEN``, ``CLOSE``, ``ATOM`` (unquoted keyword or number),
    ``QSTRING`` (quoted string with escapes resolved).
    """
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # Whitespace -- skip
        if ch in " \t\n\r":
            i += 1
            continue

        # Line comment -- skip to end of line
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue

        # Open paren
        if ch == "(":
            yield Token(TokenKind.OPEN, "(", i)
            i += 1
            continue

        # Close paren
        if ch == ")":
            yield Token(TokenKind.CLOSE, ")", i)
            i += 1
            continue

        # Quoted string
        if ch == '"':
            start = i
            i += 1  # skip opening quote
            parts: list[str] = []
            while i < n:
                c = text[i]
                if c == "\\":
                    i += 1
                    if i >= n:
                        raise SexprError(f"Unterminated escape at byte {i - 1}")
                    esc = text[i]
                    parts.append(_ESCAPES.get(esc, esc))
                    i += 1
                elif c == '"':
                    i += 1  # skip closing quote
                    break
                else:
                    parts.append(c)
                    i += 1
            else:
                raise SexprError(f"Unterminated string starting at byte {start}")
            yield Token(TokenKind.QSTRING, "".join(parts), start)
            continue

        # Unquoted atom (keyword or number)
        start = i
        while i < n and text[i] not in ' \t\n\r()";':
            i += 1
        yield Token(TokenKind.ATOM, text[start:i], start)


# -- Parser ---


def parse(text: str) -> list[SExpr]:
    """
    Parse *text* and return all top-level S-expressions.

    Returns a list -- typically one element for a KiCad file, but the
    parser handles multiple top-level forms.
    """
    tokens = list(tokenize(text))
    if not tokens:
        raise SexprError("Empty input")
    result: list[SExpr] = []
    i = 0
    n = len(tokens)

    def _parse_expr(pos: int) -> tuple[SExpr, int]:
        tok = tokens[pos]
        if tok.kind is TokenKind.OPEN:
            children: list[SExpr] = []
            pos += 1
            while pos < n and tokens[pos].kind is not TokenKind.CLOSE:
                child, pos = _parse_expr(pos)
                children.append(child)
            if pos >= n:
                raise SexprError(f"Unmatched '(' at byte {tok.offset}")
            pos += 1  # skip CLOSE
            return children, pos
        if tok.kind is TokenKind.CLOSE:
            raise SexprError(f"Unexpected ')' at byte {tok.offset}")
        # ATOM or QSTRING
        quoted = tok.kind is TokenKind.QSTRING
        return Atom(tok.value, quoted=quoted), pos + 1

    while i < n:
        expr, i = _parse_expr(i)
        result.append(expr)
    return result


def parse_one(text: str) -> SExpr:
    """
    Parse *text* expecting exactly one top-level form.

    Raises :class:`SexprError` if the input contains zero or more than one
    top-level expression.
    """
    forms = parse(text)
    if len(forms) != 1:
        raise SexprError(f"Expected exactly one expression, got {len(forms)}")
    return forms[0]


# -- Tree helpers ---


def find_all(expr: list, tag: str) -> list[list]:
    """Return all direct children of *expr* that are lists with *tag* as first element."""
    return [
        child for child in expr if isinstance(child, list) and child and child[0] == tag
    ]


def find_one(expr: list, tag: str) -> list | None:
    """Return the first direct child list with *tag*, or ``None``."""
    for child in expr:
        if isinstance(child, list) and child and child[0] == tag:
            return child
    return None


def set_child(expr: list, tag: str, child: list) -> None:
    """
    Replace the first direct child with *tag*, or append *child* if none exists.
    """
    for i, elem in enumerate(expr):
        if isinstance(elem, list) and elem and elem[0] == tag:
            expr[i] = child
            return
    expr.append(child)


def remove_children(expr: list, tag: str) -> int:
    """Remove all direct children with *tag*.  Returns the number removed."""
    before = len(expr)
    expr[:] = [
        elem
        for elem in expr
        if not (isinstance(elem, list) and elem and elem[0] == tag)
    ]
    return before - len(expr)


# -- Writer ---


def _needs_quoting(s: str) -> bool:
    """Return True if *s* must be quoted when written."""
    if not s:
        return True
    if s.startswith("#"):
        return True
    for ch in s:
        if ch in ' \t\n\r()"\\;':
            return True
    return False


def _write_atom(s: str) -> str:
    """Format a single atom for output."""
    if isinstance(s, Atom) and s.quoted:
        return f'"{_escape(s)}"'
    if _needs_quoting(s):
        return f'"{_escape(s)}"'
    return s


def _escape(s: str) -> str:
    """Backslash-escape a string for writing inside quotes."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _is_simple_list(expr: list) -> bool:
    """True if this list should be written on a single line."""
    if not expr:
        return True
    # Single-element value lists: (tag value) or (tag)
    if len(expr) <= 2 and all(isinstance(e, str) for e in expr):
        return True
    # Shortform tags
    if isinstance(expr[0], str) and expr[0] in _SHORTFORM_TAGS:
        return True
    return False


def _write_flat(expr: list) -> str:
    """Write a list on a single line."""
    parts: list[str] = []
    for elem in expr:
        if isinstance(elem, str):
            parts.append(_write_atom(elem))
        elif isinstance(elem, list):
            parts.append(_write_flat(elem))
        else:
            parts.append(str(elem))
    return "(" + " ".join(parts) + ")"


def _write_pts(expr: list, indent: str) -> str:
    """
    Write a ``(pts ...)`` list compactly, wrapping at ~99 columns.
    """
    tag = _write_atom(expr[0])
    # Collect all xy children as flat strings
    xy_parts = []
    for child in expr[1:]:
        if isinstance(child, list):
            xy_parts.append(_write_flat(child))
        else:
            xy_parts.append(_write_atom(child))

    # Try all on one line first
    one_line = f"({tag} " + " ".join(xy_parts) + ")"
    if len(indent) + len(one_line) <= _PTS_MAX_COL:
        return one_line

    # Wrap: each xy on its own line
    inner_indent = indent + "\t"
    lines = [f"({tag}"]
    for part in xy_parts:
        lines.append(f"{inner_indent}{part}")
    lines.append(f"{indent})")
    return "\n".join(lines)


def _write_expr(expr: SExpr, indent: str) -> str:
    """Recursively format an expression with KiCad v8 conventions."""
    if isinstance(expr, str):
        return _write_atom(expr)

    if not expr:
        return "()"

    # Simple / shortform lists -- single line
    if _is_simple_list(expr):
        return _write_flat(expr)

    tag = expr[0] if isinstance(expr[0], str) else None

    # pts gets special compact formatting
    if tag == "pts":
        return _write_pts(expr, indent)

    # Split children into leading atoms and the rest.  KiCad keeps
    # the tag and any leading string atoms on the opening line:
    #   (property "Reference" "R"
    #       (at 2.032 0.508 0)
    #       ...
    #   )
    if tag is not None:
        children = expr[1:]
    else:
        children = list(expr)

    # Count leading atoms (strings that appear before any sublist)
    lead_count = 0
    for child in children:
        if isinstance(child, str):
            lead_count += 1
        else:
            break
    leading = children[:lead_count]
    rest = children[lead_count:]

    # Build the opening line: (tag atom1 atom2 ...
    opener_parts = [_write_atom(tag)] if tag is not None else []
    for atom in leading:
        opener_parts.append(_write_atom(atom))
    opener = "(" + " ".join(opener_parts)

    # If no complex children remain, close inline
    if not rest:
        return opener + ")"

    # Check if remaining children are all simple
    all_simple = all(
        isinstance(c, str) or (isinstance(c, list) and _is_simple_list(c)) for c in rest
    )
    if all_simple and len(rest) <= 3 and not leading:
        # Inline: (tag child1 child2 child3)
        inline_parts = [opener]
        for child in rest:
            if isinstance(child, str):
                inline_parts.append(_write_atom(child))
            else:
                inline_parts.append(_write_flat(child))
        return " ".join(inline_parts) + ")"

    # Multi-line: opening line, then indented children, then closing paren
    lines: list[str] = [opener]
    child_indent = indent + "\t"
    for child in rest:
        if isinstance(child, str):
            lines.append(f"{child_indent}{_write_atom(child)}")
        elif isinstance(child, list):
            child_str = _write_expr(child, child_indent)
            lines.append(f"{child_indent}{child_str}")

    lines.append(f"{indent})")
    return "\n".join(lines)


def dumps(expr: SExpr) -> str:
    """
    Format an S-expression tree as a string using KiCad v8 conventions.

    Tab indentation, shortform tags on one line, compact ``pts``, closing
    paren on its own line for multi-line lists.
    """
    return _write_expr(expr, "") + "\n"
