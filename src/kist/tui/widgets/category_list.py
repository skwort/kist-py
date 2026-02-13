"""Category sidebar -- OptionList with part counts."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class CategoryList(OptionList):
    """Category sidebar with part counts."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    class Selected(Message):
        """Posted when a category is selected."""

        def __init__(self, category: str | None) -> None:
            super().__init__()
            self.category = category

    def populate(self, categories: dict[str, int]) -> None:
        """
        Rebuild the option list from category codes and counts.

        *categories* maps category code to part count. An "All" entry
        is prepended with the total. Zero-count categories are skipped.
        """
        self.clear_options()
        total = sum(categories.values())
        self.add_option(Option(f"All  ({total})", id="__all__"))
        for code in sorted(categories):
            count = categories[code]
            if count == 0:
                continue
            self.add_option(Option(f"{code}  ({count})", id=code))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        category = None if option_id == "__all__" else option_id
        self.post_message(self.Selected(category))
