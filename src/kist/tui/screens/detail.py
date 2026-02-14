"""Detail modal -- view, edit, and delete a part from the browse screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from kist.core.config import load_library_config
from kist.core.database import PartsDatabase
from kist.models.part import Part
from kist.tui.save import ValidationNotice, build_part_from_form
from kist.tui.widgets.part_form import PartForm

if TYPE_CHECKING:
    from kist.tui.app import KistApp


class DetailModal(ModalScreen[bool]):
    """
    Modal showing full part details in PartForm readonly mode.

    Returns True on dismiss if the underlying data changed (edit/delete),
    so the browse screen knows to refresh.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("e", "toggle_edit", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, part: Part) -> None:
        super().__init__()
        self._part = part
        self._changed = False
        self._form_snapshot: dict = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield PartForm(mode="readonly", id="detail-form")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#detail-container").border_title = self._part.name
        self.call_after_refresh(self._load_part)

    def _load_part(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        form.load_part(self._part)
        self._form_snapshot = form.to_dict()
        # Reset focus so nothing inside the readonly form is focused
        self.set_focus(None)

    def _form_dirty(self) -> bool:
        """Check if form values differ from the loaded snapshot."""
        form = self.query_one("#detail-form", PartForm)
        return form.to_dict() != self._form_snapshot

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show edit/delete in readonly mode, save in edit mode."""
        form = self.query_one("#detail-form", PartForm)
        editable = form.mode == "editable"
        if action == "save":
            return editable
        if action in ("toggle_edit", "delete"):
            return not editable
        return True

    # -- Edit ---

    def action_toggle_edit(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        form.mode = "editable" if form.mode == "readonly" else "readonly"
        self.refresh_bindings()

    def action_save(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        if form.mode != "editable":
            return

        app: KistApp = self.app  # type: ignore[assignment]
        library_path = app.library_path
        if not library_path:
            self.notify("No library found", severity="error")
            return

        config = load_library_config(library_path)
        d = form.to_dict()

        try:
            new_part = build_part_from_form(d, config.categories, config.separator)
        except ValidationNotice as exc:
            self.notify(str(exc), severity="error")
            return
        except Exception as exc:
            msg = str(exc).replace("[", "\\[")
            self.notify(f"Invalid part data: {msg}", severity="error")
            return

        db = PartsDatabase(library_path / "parts.json")
        db.load()

        # Remove old, add new (IPN may change since name changed)
        assert self._part.ipn is not None
        db.remove(self._part.ipn)
        db.add(new_part)

        self._part = new_part
        self._changed = True
        self._form_snapshot = form.to_dict()
        self.query_one("#detail-container").border_title = new_part.name
        form.mode = "readonly"
        self.refresh_bindings()
        self.notify(f"Saved: {new_part.name}")

    # -- Delete ---

    def action_delete(self) -> None:
        self.app.push_screen(
            ConfirmModal(f"Delete {self._part.name}?"),
            callback=self._on_delete_confirmed,
        )  # type: ignore[arg-type]

    def _on_delete_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return

        app: KistApp = self.app  # type: ignore[assignment]
        library_path = app.library_path
        if not library_path:
            return

        db = PartsDatabase(library_path / "parts.json")
        db.load()
        assert self._part.ipn is not None
        db.remove(self._part.ipn)
        self.dismiss(True)

    # -- Close ---

    def action_close(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        if form.mode == "editable":
            if self._form_dirty():
                self.app.push_screen(
                    ConfirmModal("Discard unsaved changes?"),
                    callback=self._on_discard_confirmed,
                )  # type: ignore[arg-type]
            else:
                self._switch_to_readonly()
            return
        self.dismiss(self._changed)

    def _switch_to_readonly(self) -> None:
        """Revert form to readonly, restoring the snapshot values."""
        form = self.query_one("#detail-form", PartForm)
        form.clear()
        form.load_part(self._part)
        form.mode = "readonly"
        self._form_snapshot = form.to_dict()
        self.refresh_bindings()

    def _on_discard_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self._switch_to_readonly()


class ConfirmModal(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="confirm-cancel", variant="default")
                yield Button("Confirm", id="confirm-ok", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-ok")

    def action_cancel(self) -> None:
        self.dismiss(False)
