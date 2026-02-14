"""CategoryFormModal and CategoryManagerModal tests."""

import pytest
from textual.app import App
from textual.widgets import DataTable, Input, Select

from kist.core.config import load_library_config, save_library_config
from kist.core.database import create_empty
from kist.models.config import CategoryDef, LibraryConfig
from kist.tui.modals.categories import CategoryFormModal, CategoryManagerModal


class ModalApp(App):
    CSS = ""


# -- CategoryFormModal ---


async def test_create_mode_empty_form():
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(CategoryFormModal())
        code = app.screen.query_one("#cat-code", Input)
        assert code.value == ""
        assert not code.disabled


async def test_edit_mode_populates_fields():
    cat = CategoryDef(
        name="Resistors",
        refdes="R",
        key_specs=["resistance", "tolerance"],
        value_field="resistance",
        symbol_template="resistor",
        subcategory_names={"TF": "Thick Film", "MF": "Metal Film"},
    )
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(CategoryFormModal(edit=("RES", cat)))
        assert app.screen.query_one("#cat-code", Input).value == "RES"
        assert app.screen.query_one("#cat-code", Input).disabled
        assert app.screen.query_one("#cat-name", Input).value == "Resistors"
        assert app.screen.query_one("#cat-refdes", Input).value == "R"
        assert (
            app.screen.query_one("#cat-keyspecs", Input).value
            == "resistance, tolerance"
        )
        assert app.screen.query_one("#cat-valuefield", Input).value == "resistance"
        assert app.screen.query_one("#cat-template", Select).value == "resistor"


async def test_cancel_returns_none():
    results: list = []
    app = ModalApp()
    async with app.run_test() as pilot:
        app.push_screen(CategoryFormModal(), callback=results.append)
        await pilot.pause()
        await pilot.press("escape")
        assert results == [None]


async def test_save_returns_category():
    results: list = []
    app = ModalApp()
    async with app.run_test() as pilot:
        app.push_screen(CategoryFormModal(), callback=results.append)
        await pilot.pause()
        app.screen.query_one("#cat-code", Input).value = "OPTO"
        app.screen.query_one("#cat-name", Input).value = "Optocouplers"
        app.screen.query_one("#cat-refdes", Input).value = "U"
        await pilot.press("ctrl+s")
        assert len(results) == 1
        code, cat_def = results[0]
        assert code == "OPTO"
        assert cat_def.name == "Optocouplers"
        assert cat_def.refdes == "U"


async def test_save_validates_required_fields():
    """Save with empty required fields shows error, doesn't dismiss."""
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(CategoryFormModal())
        await pilot.press("ctrl+s")
        # Modal should still be open
        assert isinstance(app.screen, CategoryFormModal)


# -- CategoryManagerModal ---


@pytest.fixture
def library_path(tmp_path):
    """Create a minimal library with two categories."""
    config = LibraryConfig(
        categories={
            "RES": CategoryDef(
                name="Resistors",
                refdes="R",
                key_specs=["resistance", "tolerance"],
                symbol_template="resistor",
            ),
            "CAP": CategoryDef(
                name="Capacitors",
                refdes="C",
                key_specs=["capacitance", "voltage_rating"],
                symbol_template="capacitor",
            ),
        }
    )
    save_library_config(tmp_path, config)
    create_empty(tmp_path / "parts.json")
    return tmp_path


async def test_manager_loads_categories(library_path):
    app = ModalApp()
    async with app.run_test():
        await app.push_screen(CategoryManagerModal(library_path))
        table = app.screen.query_one("#catmgr-table", DataTable)
        assert table.row_count == 2


async def test_manager_add_category(library_path):
    """Add via the form modal persists to config."""
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(CategoryManagerModal(library_path))
        await pilot.press("a")
        await pilot.pause()
        # Fill the form
        app.screen.query_one("#cat-code", Input).value = "DIO"
        app.screen.query_one("#cat-name", Input).value = "Diodes"
        app.screen.query_one("#cat-refdes", Input).value = "D"
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Table updated
        table = app.screen.query_one("#catmgr-table", DataTable)
        assert table.row_count == 3
        # Config persisted
        config = load_library_config(library_path)
        assert "DIO" in config.categories


async def test_manager_edit_category(library_path):
    """Edit updates the category in config."""
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(CategoryManagerModal(library_path))
        # Select first row (RES) and edit
        await pilot.press("e")
        await pilot.pause()
        # Change name
        app.screen.query_one("#cat-name", Input).value = "Resistors (Updated)"
        await pilot.press("ctrl+s")
        await pilot.pause()
        config = load_library_config(library_path)
        assert config.categories["RES"].name == "Resistors (Updated)"


async def test_manager_delete_category(library_path):
    """Delete removes category from config."""
    app = ModalApp()
    async with app.run_test() as pilot:
        await app.push_screen(CategoryManagerModal(library_path))
        await pilot.press("d")
        await pilot.pause()
        # Confirm deletion
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        config = load_library_config(library_path)
        # One category removed
        assert len(config.categories) == 1
