"""Custom themes for the kist TUI."""

from textual.theme import Theme

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
