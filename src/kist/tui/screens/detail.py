"""Detail modal -- view, edit, and delete a part from the browse screen."""

from __future__ import annotations

from textual import getters
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from kist.models.part import Part
from kist.tui.app import KistApp
from kist.tui.save import ValidationNotice, build_part_from_form
from kist.tui.widgets.part_form import PartForm


class DetailModal(ModalScreen):
    """
    Modal showing full part details in PartForm readonly mode.
    """

    app = getters.app(KistApp)

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("e", "toggle_edit", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, part: Part) -> None:
        super().__init__()
        self._part = part
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
        config = self.app.library_config
        if config:
            form.set_categories(config.categories)
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

        config = self.app.library_config
        if not config:
            self.notify("No library found", severity="error")
            return

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

        assert self._part.ipn is not None
        self.app.save_part(new_part, replacing=self._part.ipn)

        self._part = new_part
        form.clear()
        form.load_part(new_part)
        self.query_one("#detail-container").border_title = new_part.name
        form.mode = "readonly"
        self._form_snapshot = form.to_dict()
        self.refresh_bindings()
        self.notify(f"Saved: {new_part.name}")

    # -- Delete ---

    def action_delete(self) -> None:
        self.app.push_screen(
            ConfirmModal(f"Delete {self._part.name}?"),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return

        assert self._part.ipn is not None
        self.app.delete_part(self._part.ipn)
        self.dismiss()

    # -- Close ---

    def action_close(self) -> None:
        form = self.query_one("#detail-form", PartForm)
        if form.mode == "editable":
            if self._form_dirty():
                self.app.push_screen(
                    ConfirmModal("Discard unsaved changes?"),
                    callback=self._on_discard_confirmed,
                )
            else:
                self._switch_to_readonly()
            return
        self.dismiss()

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
                yield Button("Confirm", id="confirm-ok", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-ok")

    def action_cancel(self) -> None:
        self.dismiss(False)
