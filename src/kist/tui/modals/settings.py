"""Settings modal -- user preferences and library configuration."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from kist.core.config import (
    load_global_config,
    load_library_config,
    save_global_config,
    save_library_config,
)


def _theme_options() -> list[tuple[str, str]]:
    """Build select options from Textual's registered themes."""
    # Textual ships built-in themes; we add kist-dark alongside them.
    # The full list is discovered at runtime from the app, but for the
    # select widget we use a curated list of well-known themes.
    return [
        ("kist-dark", "kist-dark"),
        ("textual-dark", "textual-dark"),
        ("textual-light", "textual-light"),
        ("nord", "nord"),
        ("gruvbox", "gruvbox"),
        ("catppuccin-mocha", "catppuccin-mocha"),
        ("dracula", "dracula"),
        ("tokyo-night", "tokyo-night"),
        ("monokai", "monokai"),
        ("flexoki", "flexoki"),
        ("catppuccin-latte", "catppuccin-latte"),
        ("solarized-light", "solarized-light"),
    ]


class SettingsModal(ModalScreen):
    """
    Scrollable settings form with appearance and library configuration.

    Theme changes apply immediately as a live preview. Cancel reverts
    the theme to its previous value.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, library_path: Path | None = None) -> None:
        super().__init__()
        self._library_path = library_path
        self._previous_theme: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")
            with VerticalScroll(id="settings-scroll"):
                # Appearance section
                with Vertical(classes="section", id="section-appearance"):
                    with Horizontal(classes="form-field"):
                        yield Label("Theme", classes="field-label")
                        yield Select(
                            _theme_options(),
                            id="setting-theme",
                            classes="field-value",
                            prompt="Select theme",
                        )

                # Library section (only when a library is open)
                if self._library_path is not None:
                    with Vertical(classes="section", id="section-library"):
                        with Horizontal(classes="form-field"):
                            yield Label("Prefix", classes="field-label")
                            yield Input(
                                id="setting-prefix",
                                classes="field-value",
                            )
                        with Horizontal(classes="form-field"):
                            yield Label("Separator", classes="field-label")
                            yield Input(
                                id="setting-separator",
                                classes="field-value",
                            )
                        with Horizontal(classes="form-field"):
                            yield Label("Suppliers", classes="field-label")
                            yield Input(
                                id="setting-suppliers",
                                classes="field-value",
                                placeholder="Comma-separated",
                            )

                    # Directories section
                    with Vertical(classes="section", id="section-directories"):
                        with Horizontal(classes="form-field"):
                            yield Label("Symbols", classes="field-label")
                            yield Input(
                                id="setting-symbols-dir",
                                classes="field-value",
                            )
                        with Horizontal(classes="form-field"):
                            yield Label("Footprints", classes="field-label")
                            yield Input(
                                id="setting-footprints-dir",
                                classes="field-value",
                            )
                        with Horizontal(classes="form-field"):
                            yield Label("3D Models", classes="field-label")
                            yield Input(
                                id="setting-models-dir",
                                classes="field-value",
                            )

            # Action buttons
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="settings-cancel", variant="default")
                yield Button("Save", id="settings-save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#section-appearance").border_title = "Appearance"

        # Load current values
        self._previous_theme = self.app.theme or "kist-dark"
        global_cfg = load_global_config()
        self.query_one("#setting-theme", Select).value = global_cfg.theme

        if self._library_path is not None:
            self.query_one("#section-library").border_title = "Library"
            self.query_one("#section-directories").border_title = "Directories"

            lib_cfg = load_library_config(self._library_path)
            self.query_one("#setting-prefix", Input).value = lib_cfg.library_prefix
            self.query_one("#setting-separator", Input).value = lib_cfg.separator
            self.query_one("#setting-suppliers", Input).value = ", ".join(
                lib_cfg.suppliers
            )
            self.query_one("#setting-symbols-dir", Input).value = lib_cfg.symbols_dir
            self.query_one(
                "#setting-footprints-dir", Input
            ).value = lib_cfg.footprints_dir
            self.query_one("#setting-models-dir", Input).value = lib_cfg.models_dir

    # -- Live theme preview ---

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "setting-theme" and event.value != Select.BLANK:
            self.app.theme = str(event.value)

    # -- Button handlers ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-save":
            self.action_save()
        elif event.button.id == "settings-cancel":
            self.action_cancel()

    # -- Actions ---

    def action_save(self) -> None:
        # Save appearance to global config
        global_cfg = load_global_config()
        theme_val = self.query_one("#setting-theme", Select).value
        if theme_val != Select.BLANK:
            global_cfg.theme = str(theme_val)
        save_global_config(global_cfg)

        # Save library fields if a library is open
        if self._library_path is not None:
            lib_cfg = load_library_config(self._library_path)
            lib_cfg.library_prefix = self.query_one(
                "#setting-prefix", Input
            ).value.strip()
            lib_cfg.separator = self.query_one(
                "#setting-separator", Input
            ).value.strip()
            suppliers_raw = self.query_one("#setting-suppliers", Input).value.strip()
            lib_cfg.suppliers = [
                s.strip() for s in suppliers_raw.split(",") if s.strip()
            ]
            lib_cfg.symbols_dir = self.query_one(
                "#setting-symbols-dir", Input
            ).value.strip()
            lib_cfg.footprints_dir = self.query_one(
                "#setting-footprints-dir", Input
            ).value.strip()
            lib_cfg.models_dir = self.query_one(
                "#setting-models-dir", Input
            ).value.strip()
            save_library_config(self._library_path, lib_cfg)

        self._previous_theme = self.app.theme or "kist-dark"
        self.dismiss()

    def action_cancel(self) -> None:
        self.app.theme = self._previous_theme
        self.dismiss()
