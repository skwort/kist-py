"""CategoryFormModal tests -- create mode, edit mode, cancel."""

from textual.app import App
from textual.widgets import Input, Select

from kist.models.config import CategoryDef
from kist.tui.modals.categories import CategoryFormModal


class ModalApp(App):
    CSS = ""


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
