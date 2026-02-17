"""Theme adapter tests for KiCad preview renderer."""

from kist.tui.themes import NULL_THEME, render_theme_from_textual


def test_render_theme_from_textual_none_uses_defaults():
    theme = render_theme_from_textual(None)
    assert theme.symbol_fg == (179, 179, 179, 255)
    assert theme.footprint_silk == (185, 185, 185, 255)


def test_render_theme_from_null_theme():
    theme = render_theme_from_textual(NULL_THEME)
    assert theme.symbol_fg == (179, 179, 179, 255)
    assert theme.footprint_silk == (179, 179, 179, 255)
    assert theme.footprint_fab == (85, 85, 85, 220)
    assert theme.footprint_courtyard == (205, 205, 85, 180)
    assert theme.footprint_copper == (204, 85, 204, 230)
    assert theme.footprint_pad == (204, 85, 204, 180)
