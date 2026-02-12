"""Tests for the S-expression tokenizer, parser, writer, and tree helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from kist.sexpr import (
    Atom,
    SexprError,
    TokenKind,
    dumps,
    find_all,
    find_one,
    parse,
    parse_one,
    remove_children,
    set_child,
    tokenize,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kicad"
_FIXTURE_FILES = sorted(FIXTURES.glob("*.kicad_sym"))


# -- Atom ---


def test_atom_unquoted():
    a = Atom("hello", quoted=False)
    assert a == "hello"
    assert a.quoted is False


def test_atom_quoted():
    a = Atom("hello world", quoted=True)
    assert a == "hello world"
    assert a.quoted is True


def test_atom_str_operations():
    a = Atom("abc", quoted=True)
    assert a.upper() == "ABC"
    assert a + "d" == "abcd"
    assert len(a) == 3


def test_atom_repr():
    a = Atom("x", quoted=True)
    assert "Atom" in repr(a)
    assert "quoted=True" in repr(a)


def test_atom_default_unquoted():
    a = Atom("test")
    assert a.quoted is False


# -- Tokenizer ---


def test_tokenize_simple_list():
    tokens = list(tokenize("(kicad_symbol_lib)"))
    assert len(tokens) == 3
    assert tokens[0].kind is TokenKind.OPEN
    assert tokens[1].kind is TokenKind.ATOM
    assert tokens[1].value == "kicad_symbol_lib"
    assert tokens[2].kind is TokenKind.CLOSE


def test_tokenize_nested():
    tokens = list(tokenize("(a (b c))"))
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.OPEN,
        TokenKind.ATOM,
        TokenKind.OPEN,
        TokenKind.ATOM,
        TokenKind.ATOM,
        TokenKind.CLOSE,
        TokenKind.CLOSE,
    ]


def test_tokenize_quoted_string():
    tokens = list(tokenize('(property "Reference" "R")'))
    assert tokens[2].kind is TokenKind.QSTRING
    assert tokens[2].value == "Reference"
    assert tokens[3].kind is TokenKind.QSTRING
    assert tokens[3].value == "R"


def test_tokenize_escape_sequences():
    tokens = list(tokenize(r'("hello \"world\"")'))
    assert tokens[1].value == 'hello "world"'


def test_tokenize_escape_backslash():
    tokens = list(tokenize(r'("path\\to\\file")'))
    assert tokens[1].value == "path\\to\\file"


def test_tokenize_escape_newline():
    tokens = list(tokenize(r'("line1\nline2")'))
    assert tokens[1].value == "line1\nline2"


def test_tokenize_escape_carriage_return():
    tokens = list(tokenize(r'("with\rreturn")'))
    assert tokens[1].value == "with\rreturn"


def test_tokenize_line_comment():
    tokens = list(tokenize("(a ; comment\n b)"))
    values = [t.value for t in tokens if t.kind is TokenKind.ATOM]
    assert values == ["a", "b"]


def test_tokenize_whitespace_variations():
    tokens = list(tokenize("( a\tb\n\rc )"))
    values = [t.value for t in tokens if t.kind is TokenKind.ATOM]
    assert values == ["a", "b", "c"]


def test_tokenize_numbers_as_atoms():
    tokens = list(tokenize("(width 0.254)"))
    assert tokens[2].kind is TokenKind.ATOM
    assert tokens[2].value == "0.254"


def test_tokenize_negative_number():
    tokens = list(tokenize("(at -2.54 0)"))
    values = [t.value for t in tokens if t.kind is TokenKind.ATOM]
    assert values == ["at", "-2.54", "0"]


def test_tokenize_hash_prefixed_atom():
    # #-prefixed values in KiCad are sometimes unquoted in source
    tokens = list(tokenize("(color #ff0000)"))
    assert tokens[2].value == "#ff0000"


def test_tokenize_offsets():
    tokens = list(tokenize("(ab cd)"))
    assert tokens[0].offset == 0  # (
    assert tokens[1].offset == 1  # ab
    assert tokens[2].offset == 4  # cd
    assert tokens[3].offset == 6  # )


def test_tokenize_empty_quoted_string():
    tokens = list(tokenize('(name "")'))
    assert tokens[2].kind is TokenKind.QSTRING
    assert tokens[2].value == ""


def test_tokenize_unterminated_string():
    with pytest.raises(SexprError, match="Unterminated string"):
        list(tokenize('("hello'))


def test_tokenize_unterminated_escape():
    with pytest.raises(SexprError, match="Unterminated escape"):
        list(tokenize('("hello\\'))


def test_tokenize_empty_input():
    tokens = list(tokenize(""))
    assert tokens == []


def test_tokenize_only_whitespace():
    tokens = list(tokenize("   \n\t  "))
    assert tokens == []


def test_tokenize_semicolon_not_in_string():
    tokens = list(tokenize('("semi;colon")'))
    assert tokens[1].value == "semi;colon"


def test_tokenize_multiple_top_level():
    tokens = list(tokenize("(a) (b)"))
    opens = [t for t in tokens if t.kind is TokenKind.OPEN]
    assert len(opens) == 2


# -- Parser ---


def test_parse_simple_list():
    result = parse("(hello)")
    assert result == [["hello"]]


def test_parse_nested_list():
    result = parse("(a (b c) d)")
    assert result == [["a", ["b", "c"], "d"]]


def test_parse_multiple_top_level():
    result = parse("(a) (b)")
    assert len(result) == 2
    assert result[0] == ["a"]
    assert result[1] == ["b"]


def test_parse_atoms_are_atom_type():
    result = parse('(key "value")')
    assert isinstance(result[0][0], Atom)
    assert result[0][0].quoted is False
    assert isinstance(result[0][1], Atom)
    assert result[0][1].quoted is True


def test_parse_deeply_nested():
    result = parse("(a (b (c (d e))))")
    assert result == [["a", ["b", ["c", ["d", "e"]]]]]


def test_parse_empty_list():
    result = parse("()")
    assert result == [[]]


def test_parse_empty_input():
    with pytest.raises(SexprError, match="Empty input"):
        parse("")


def test_parse_unmatched_open():
    with pytest.raises(SexprError, match="Unmatched"):
        parse("(a (b)")


def test_parse_unexpected_close():
    with pytest.raises(SexprError, match="Unexpected"):
        parse(")")


def test_parse_kicad_symbol_snippet():
    text = """
    (kicad_symbol_lib
        (version 20231120)
        (generator "kist")
        (symbol "RES-10K-1PCT-0603"
            (property "Reference" "R")
            (property "Value" "10k")
        )
    )
    """
    result = parse_one(text)
    assert isinstance(result, list)
    assert result[0] == "kicad_symbol_lib"
    assert find_one(result, "version") == ["version", "20231120"]
    sym = find_one(result, "symbol")
    assert sym is not None
    assert sym[1] == "RES-10K-1PCT-0603"


def test_parse_numbers_preserved_as_strings():
    result = parse_one("(width 0.254)")
    assert result[1] == "0.254"
    assert isinstance(result[1], str)


def test_parse_one_single():
    result = parse_one("(hello)")
    assert result == ["hello"]


def test_parse_one_multiple_raises():
    with pytest.raises(SexprError, match="Expected exactly one"):
        parse_one("(a) (b)")


def test_parse_one_bare_atom():
    result = parse_one("hello")
    assert result == "hello"


# -- Tree helpers ---


def test_find_all_matching():
    tree = ["sym", ["property", "A"], ["pin", "1"], ["property", "B"]]
    props = find_all(tree, "property")
    assert len(props) == 2
    assert props[0] == ["property", "A"]
    assert props[1] == ["property", "B"]


def test_find_all_no_match():
    tree = ["sym", ["pin", "1"]]
    assert find_all(tree, "property") == []


def test_find_all_ignores_atoms():
    tree = ["sym", "property", ["property", "A"]]
    props = find_all(tree, "property")
    assert len(props) == 1


def test_find_all_only_direct_children():
    tree = ["a", ["b", ["property", "nested"]], ["property", "direct"]]
    props = find_all(tree, "property")
    assert len(props) == 1
    assert props[0] == ["property", "direct"]


def test_find_one_finds_first():
    tree = ["sym", ["property", "A"], ["property", "B"]]
    result = find_one(tree, "property")
    assert result == ["property", "A"]


def test_find_one_not_found():
    tree = ["sym", ["pin", "1"]]
    assert find_one(tree, "property") is None


def test_set_child_replaces_existing():
    tree = ["sym", ["version", "1"], ["generator", "old"]]
    set_child(tree, "generator", ["generator", "kist"])
    assert tree == ["sym", ["version", "1"], ["generator", "kist"]]


def test_set_child_appends_new():
    tree = ["sym", ["version", "1"]]
    set_child(tree, "generator", ["generator", "kist"])
    assert tree == ["sym", ["version", "1"], ["generator", "kist"]]


def test_set_child_replaces_only_first():
    tree = ["sym", ["prop", "A"], ["prop", "B"]]
    set_child(tree, "prop", ["prop", "C"])
    assert tree[1] == ["prop", "C"]
    assert tree[2] == ["prop", "B"]


def test_remove_children_removes_all():
    tree = ["sym", ["prop", "A"], ["pin", "1"], ["prop", "B"]]
    count = remove_children(tree, "prop")
    assert count == 2
    assert tree == ["sym", ["pin", "1"]]


def test_remove_children_removes_none():
    tree = ["sym", ["pin", "1"]]
    count = remove_children(tree, "prop")
    assert count == 0
    assert tree == ["sym", ["pin", "1"]]


# -- Writer ---


def test_dumps_simple_list():
    result = dumps(["version", "20231120"])
    assert result == "(version 20231120)\n"


def test_dumps_single_atom():
    result = dumps("hello")
    assert result == "hello\n"


def test_dumps_quoted_atom():
    result = dumps(Atom("hello world", quoted=True))
    assert result == '"hello world"\n'


def test_dumps_auto_quoting_spaces():
    result = dumps(["property", Atom("has spaces", quoted=False)])
    assert '"has spaces"' in result


def test_dumps_auto_quoting_empty():
    result = dumps(["name", Atom("", quoted=True)])
    assert '""' in result


def test_dumps_auto_quoting_hash():
    result = dumps(["value", "#power"])
    assert '"#power"' in result


def test_dumps_preserves_original_quoting():
    result = dumps(["property", Atom("Reference", quoted=True)])
    assert '"Reference"' in result


def test_dumps_shortform_font():
    expr = ["font", ["size", "1.27", "1.27"]]
    result = dumps(expr)
    assert "\n" not in result.strip()


def test_dumps_shortform_stroke():
    expr = ["stroke", ["width", "0"], ["type", "default"]]
    result = dumps(expr)
    assert "\n" not in result.strip()


def test_dumps_shortform_fill():
    expr = ["fill", ["type", "none"]]
    result = dumps(expr)
    assert "\n" not in result.strip()


def test_dumps_shortform_at():
    expr = ["at", "0", "0"]
    result = dumps(expr)
    assert result == "(at 0 0)\n"


def test_dumps_leading_atoms_on_opening_line():
    """Tag and leading string atoms stay on the opening line."""
    expr = [
        "symbol",
        Atom("R", quoted=True),
        ["property", Atom("Reference", quoted=True), Atom("R", quoted=True)],
    ]
    result = dumps(expr)
    assert result.startswith('(symbol "R"\n')


def test_dumps_property_with_children():
    """Property tag + key + value on opening line, children indented."""
    expr = [
        "property",
        Atom("Reference", quoted=True),
        Atom("R", quoted=True),
        ["at", "2.032", "0.508", "0"],
    ]
    result = dumps(expr)
    first_line = result.split("\n")[0]
    assert first_line == '(property "Reference" "R"'


def test_dumps_nested_multiline():
    expr = [
        "kicad_symbol_lib",
        ["version", "20231120"],
        ["generator", Atom("kist", quoted=True)],
        [
            "symbol",
            Atom("R_10K", quoted=True),
            ["property", Atom("Reference", quoted=True), Atom("R", quoted=True)],
            ["property", Atom("Value", quoted=True), Atom("10k", quoted=True)],
        ],
    ]
    result = dumps(expr)
    lines = result.strip().split("\n")
    assert lines[0].startswith("(kicad_symbol_lib")
    assert any("\t" in line for line in lines[1:])
    assert lines[-1] == ")"


def test_dumps_empty_list():
    result = dumps([])
    assert result == "()\n"


def test_dumps_escape_in_output():
    expr = ["property", Atom('say "hi"', quoted=True)]
    result = dumps(expr)
    assert r"\"" in result


def test_dumps_escape_newline_in_output():
    expr = ["note", Atom("line1\nline2", quoted=True)]
    result = dumps(expr)
    assert "\\n" in result


def test_dumps_pts_compact():
    expr = [
        "pts",
        ["xy", "0", "0"],
        ["xy", "1", "1"],
        ["xy", "2", "0"],
    ]
    result = dumps(expr)
    assert result.strip().count("\n") == 0


def test_dumps_pts_wraps_when_long():
    expr = ["pts"]
    for i in range(20):
        expr.append(["xy", f"{i * 10.5432:.4f}", f"{i * 20.1234:.4f}"])
    result = dumps(expr)
    assert result.strip().count("\n") > 0


# -- Round-trip ---


def test_roundtrip_simple():
    original = "(version 20231120)\n"
    tree = parse_one(original)
    output = dumps(tree)
    reparsed = parse_one(output)
    assert tree == reparsed


def test_roundtrip_nested():
    original = """(kicad_symbol_lib
\t(version 20231120)
\t(generator "kist")
)
"""
    tree = parse_one(original)
    output = dumps(tree)
    reparsed = parse_one(output)
    assert _structural_eq(tree, reparsed)


def test_roundtrip_quoted_strings():
    original = '(property "Reference" "R")\n'
    tree = parse_one(original)
    output = dumps(tree)
    reparsed = parse_one(output)
    assert _structural_eq(tree, reparsed)


def test_roundtrip_escape():
    original = '(note "line1\\nline2")\n'
    tree = parse_one(original)
    output = dumps(tree)
    reparsed = parse_one(output)
    assert reparsed[1] == "line1\nline2"


def test_roundtrip_empty_string():
    original = '(name "")\n'
    tree = parse_one(original)
    output = dumps(tree)
    reparsed = parse_one(output)
    assert reparsed[1] == ""


# -- Fixture round-trip tests ---


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=[p.name for p in _FIXTURE_FILES],
)
def test_fixture_structural_roundtrip(fixture_path: Path):
    """parse(dumps(parse(file))) == parse(file) for every fixture."""
    original_text = fixture_path.read_text()
    tree = parse_one(original_text)
    written = dumps(tree)
    reparsed = parse_one(written)
    assert _structural_eq(tree, reparsed), (
        f"Structural mismatch after round-trip of {fixture_path.name}"
    )


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=[p.name for p in _FIXTURE_FILES],
)
def test_fixture_symbol_count_preserved(fixture_path: Path):
    """Same number of top-level symbols before and after round-trip."""
    text = fixture_path.read_text()
    tree = parse_one(text)
    assert isinstance(tree, list)
    symbols_before = find_all(tree, "symbol")

    written = dumps(tree)
    reparsed = parse_one(written)
    assert isinstance(reparsed, list)
    symbols_after = find_all(reparsed, "symbol")

    assert len(symbols_before) == len(symbols_after)


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=[p.name for p in _FIXTURE_FILES],
)
def test_fixture_idempotent_write(fixture_path: Path):
    """dumps(parse(dumps(parse(file)))) == dumps(parse(file))."""
    text = fixture_path.read_text()
    tree = parse_one(text)
    first_write = dumps(tree)

    tree2 = parse_one(first_write)
    second_write = dumps(tree2)

    assert first_write == second_write, f"Writer not idempotent for {fixture_path.name}"


# -- Snapshot tests ---


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=[p.name for p in _FIXTURE_FILES],
)
def test_writer_snapshot(fixture_path: Path, snapshot):
    """Snapshot the writer output for each fixture to catch formatting regressions."""
    text = fixture_path.read_text()
    tree = parse_one(text)
    written = dumps(tree)
    assert written == snapshot


# -- Helpers ---


def _structural_eq(a: object, b: object) -> bool:
    """Compare two S-expression trees, ignoring Atom.quoted metadata."""
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_structural_eq(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False
