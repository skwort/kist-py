"""Custom themes for the kist TUI."""

from textual.color import Color
from textual.theme import Theme

from kist.kicad.render import RenderTheme

NULL_THEME = Theme(
    name="null",
    primary="#333333",
    secondary="#555555",
    warning="#cdcd55",
    error="#cc5555",
    success="#53ae71",
    accent="#cc55cc",
    foreground="#b3b3b3",
    background="#000000",
    surface="#0a0a0a",
    panel="#222222",
    dark=True,
)


def _rgba_from_textual(
    color_value: str | None,
    fallback: tuple[int, int, int, int],
    alpha: int = 255,
) -> tuple[int, int, int, int]:
    if not color_value:
        return fallback
    try:
        rgb = Color.parse(color_value).rgb
    except Exception:
        return fallback
    return (rgb[0], rgb[1], rgb[2], alpha)


def render_theme_from_textual(theme: Theme | None) -> RenderTheme:
    """Build renderer palette colors from a Textual theme."""
    if theme is None:
        return RenderTheme()

    fg = _rgba_from_textual(theme.foreground, (179, 179, 179, 255))
    secondary = _rgba_from_textual(theme.secondary, (120, 150, 190, 220), alpha=220)
    warning = _rgba_from_textual(theme.warning, (210, 190, 90, 180), alpha=180)
    accent = _rgba_from_textual(theme.accent, (240, 130, 75, 230), alpha=230)
    panel = _rgba_from_textual(theme.panel, (0, 0, 0, 0), alpha=0)

    return RenderTheme(
        canvas_bg=panel,
        symbol_fg=fg,
        symbol_text=fg,
        footprint_silk=fg,
        footprint_fab=secondary,
        footprint_courtyard=warning,
        footprint_copper=accent,
        footprint_pad=(accent[0], accent[1], accent[2], 180),
        footprint_other=(fg[0], fg[1], fg[2], 160),
    )
