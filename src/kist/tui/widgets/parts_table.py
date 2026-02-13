"""Parts table -- DataTable configured for displaying Part objects."""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import DataTable

from kist.models.part import Part, Tier

TIER_ABBREV: dict[Tier, str] = {
    Tier.JELLYBEAN: "JB",
    Tier.SEMI_JELLYBEAN: "SJ",
    Tier.PROPRIETARY: "PR",
}

MAX_DESC_LEN = 40


class PartsTable(DataTable):
    """
    DataTable subclass pre-configured for part display.

    Columns: Name, Value, Package, Tier, Description.
    Uses ``part.ipn`` as the row key for later detail-modal lookup.
    """

    cursor_type = "row"
    zebra_stripes = True

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def on_mount(self) -> None:
        self.add_columns("Name", "Value", "Package", "Tier", "Description")

    def populate(self, parts: list[Part]) -> None:
        """Clear and repopulate with the given parts."""
        self.clear()
        for part in parts:
            desc = part.description
            if len(desc) > MAX_DESC_LEN:
                desc = desc[: MAX_DESC_LEN - 3] + "..."
            self.add_row(
                part.name,
                part.value,
                part.package or "",
                TIER_ABBREV.get(Tier(part.tier), part.tier),
                desc,
                key=part.ipn,
            )
