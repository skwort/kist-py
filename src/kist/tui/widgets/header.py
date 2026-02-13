"""Custom header with library path display."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static
from textual.widgets._header import Header, HeaderTitle


class HeaderPageTitle(Static):
    """Displays icon + page title on the left of the header."""

    DEFAULT_CSS = """
    HeaderPageTitle {
        dock: left;
        padding: 0 1;
        width: auto;
        content-align: left middle;
    }
    """

    async def on_click(self) -> None:
        await self.run_action("app.command_palette")


class HeaderLibraryPath(Static):
    """Displays the active library path on the right side of the header."""

    DEFAULT_CSS = """
    HeaderLibraryPath {
        dock: right;
        padding: 0 1;
        width: auto;
        max-width: 40;
        text-opacity: 60%;
        content-align: right middle;
    }
    """

    def on_mount(self) -> None:
        self.watch(self.app, "library_path", self._update_path)

    def _update_path(self, path: Path | None) -> None:
        if path is None:
            self.update("No library")
            return
        try:
            display = "~" / path.relative_to(Path.home())
        except ValueError:
            display = path
        self.update(str(display))


class KistHeader(Header):
    """Kist header -- icon and page title left, app title center, library path right."""

    def __init__(
        self,
        *,
        page_title: str = "",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, icon=icon)
        self._page_title = page_title

    def compose(self) -> ComposeResult:
        icon = self.icon or ""
        label = f"{icon} {self._page_title}" if self._page_title else icon
        yield HeaderPageTitle(label)
        yield HeaderTitle()
        yield HeaderLibraryPath()
