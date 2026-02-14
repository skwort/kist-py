"""LibraryCheckModal tests -- display issues and empty state."""

from textual.app import App
from textual.widgets import Label, Static

from kist.core.check import CheckIssue
from kist.tui.modals.check import LibraryCheckModal


class ModalApp(App):
    """Minimal app for testing modals."""

    CSS = ""


async def test_check_modal_shows_issue_count():
    issues = [
        CheckIssue(
            kind="name_drift",
            message='"WRONG" should be "RIGHT"',
            parts=["WRONG"],
        ),
        CheckIssue(
            kind="duplicate_identity",
            message="A and B share (RES, 10K)",
            parts=["A", "B"],
        ),
    ]
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibraryCheckModal(issues))
        header = app.screen.query_one("#check-header", Label)
        assert "2 issues found" in str(header.content)


async def test_check_modal_shows_all_clean():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibraryCheckModal([]))
        header = app.screen.query_one("#check-header", Label)
        assert "All clean" in str(header.content)


async def test_check_modal_shows_issue_details():
    issues = [
        CheckIssue(
            kind="name_drift",
            message='"OLD" should be "NEW"',
            parts=["OLD"],
        ),
    ]
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibraryCheckModal(issues))
        kind_labels = app.screen.query(".check-kind")
        assert len(kind_labels) == 1
        kind_label = kind_labels.first(Label)
        assert "Name drift" in str(kind_label.content)
        detail_labels = app.screen.query(".check-detail")
        detail = detail_labels.first(Static)
        assert '"OLD" should be "NEW"' in str(detail.content)


async def test_check_modal_escape_closes():
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(LibraryCheckModal([]))
        assert isinstance(app.screen, LibraryCheckModal)
        await pilot.press("escape")
        assert not isinstance(app.screen, LibraryCheckModal)


async def test_check_modal_singular_issue():
    """Single issue uses singular 'issue' not 'issues'."""
    issues = [
        CheckIssue(kind="name_drift", message="test", parts=["X"]),
    ]
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(LibraryCheckModal(issues))
        header = app.screen.query_one("#check-header", Label)
        assert "1 issue found" in str(header.content)
