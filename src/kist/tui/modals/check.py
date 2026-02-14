"""Library check results modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from kist.core.check import CheckIssue

ISSUE_LABELS: dict[str, str] = {
    "name_drift": "Name drift",
    "duplicate_identity": "Duplicate identity",
}


class LibraryCheckModal(ModalScreen):
    """
    Modal displaying library check results.

    Shows a summary header and a scrollable list of issues.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, issues: list[CheckIssue]) -> None:
        super().__init__()
        self._issues = issues

    def compose(self) -> ComposeResult:
        n = len(self._issues)
        header = f"{n} issue{'s' if n != 1 else ''} found" if n else "All clean"

        with Vertical(id="check-container") as container:
            container.border_title = header
            with VerticalScroll(id="check-results"):
                if not self._issues:
                    yield Label("No issues found.", id="check-empty")
                for issue in self._issues:
                    kind_label = ISSUE_LABELS.get(issue.kind, issue.kind)
                    yield Label(f"! {kind_label}", classes="check-kind")
                    yield Static(issue.message, classes="check-detail")

    def action_close(self) -> None:
        self.dismiss()
