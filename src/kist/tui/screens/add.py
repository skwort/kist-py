"""Add screen -- add a new part to the library."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, Static

from kist import __version__
from kist.core.config import load_global_config, load_library_config
from kist.core.database import PartsDatabase
from kist.core.naming import generate_description, generate_name, generate_value
from kist.errors import DigiKeyError, DuplicatePartError
from kist.models.part import (
    JellybeanPart,
    ProprietaryPart,
    SemiJellybeanPart,
    SupplierInfo,
    Tier,
)
from kist.providers.digikey import DigiKeyClient, parse_digikey_url
from kist.providers.models import DigiKeyProduct
from kist.tui.widgets.header import KistHeader
from kist.tui.widgets.part_form import PartForm

if TYPE_CHECKING:
    from kist.tui.app import KistApp


class AddScreen(Screen):
    """Full-screen form for adding a new part."""

    TITLE = "Kist"
    SUB_TITLE = f"v{__version__}"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        url_or_mpn: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._url_or_mpn = url_or_mpn

    def compose(self) -> ComposeResult:
        yield KistHeader(icon="\N{PACKAGE}", page_title="Add Part")
        with Horizontal(id="url-bar"):
            yield Label("URL / MPN", id="url-label")
            yield Input(id="url-input", placeholder="Paste DigiKey URL or enter MPN")
        yield Static("", id="loading-indicator")
        yield PartForm(mode="editable", id="part-form")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading-indicator").display = False
        if self._url_or_mpn:
            self.query_one("#url-input", Input).value = self._url_or_mpn
            self._start_fetch(self._url_or_mpn)

    # -- URL input ---

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            url_or_mpn = event.value.strip()
            if url_or_mpn:
                self._start_fetch(url_or_mpn)

    # -- Fetch worker ---

    def _start_fetch(self, url_or_mpn: str) -> None:
        """Parse the input and kick off a background fetch."""
        self._url_or_mpn = url_or_mpn
        try:
            product_number = parse_digikey_url(url_or_mpn)
        except DigiKeyError as exc:
            self.notify(str(exc), severity="error")
            return

        loading = self.query_one("#loading-indicator", Static)
        loading.update(f"Fetching {product_number} from DigiKey...")
        self.query_one("#loading-indicator").display = True
        self.query_one("#part-form").display = False
        self._fetch_worker()

    @work(exclusive=True)
    async def _fetch_worker(self) -> None:
        """Async worker: run blocking API call in a thread, populate form."""
        try:
            product = await asyncio.to_thread(self._fetch_product)
        except DigiKeyError as exc:
            self._show_form()
            self.notify(str(exc), severity="error")
        except Exception as exc:
            self._show_form()
            self.notify(f"Fetch failed: {exc}", severity="error")
        else:
            self._show_form()
            form = self.query_one("#part-form", PartForm)
            form.load_from_provider(product)

    def _fetch_product(self) -> DigiKeyProduct:
        """Blocking: parse URL/MPN, load credentials, call DigiKey API."""
        assert self._url_or_mpn is not None  # set by _start_fetch before worker
        product_number = parse_digikey_url(self._url_or_mpn)
        global_cfg = load_global_config()
        dk_cfg = global_cfg.providers.digikey
        # Env vars first, config file as fallback
        client_id = os.environ.get("KIST_DIGIKEY_CLIENT_ID") or dk_cfg.client_id
        client_secret = (
            os.environ.get("KIST_DIGIKEY_CLIENT_SECRET") or dk_cfg.client_secret
        )
        if not client_id or not client_secret:
            raise DigiKeyError("DigiKey credentials not configured")
        client = DigiKeyClient(client_id, client_secret)
        return client.fetch_product(product_number)

    def _show_form(self) -> None:
        """Hide loading indicator and restore the form."""
        self.query_one("#loading-indicator").display = False
        self.query_one("#part-form").display = True

    # -- Save ---

    def action_save(self) -> None:
        """Build Part from form, generate name, save to database."""
        form = self.query_one("#part-form", PartForm)
        d = form.to_dict()

        tier = d.get("tier")
        if not tier:
            self.notify("Tier is required", severity="error")
            return

        category = d.get("category")
        if not category:
            self.notify("Category is required", severity="error")
            return

        app: KistApp = self.app  # type: ignore[assignment]
        library_path = app.library_path
        if not library_path:
            self.notify("No library found -- run kist init first", severity="error")
            return

        config = load_library_config(library_path)
        categories = config.categories

        # Build SupplierInfo objects from flat dicts
        suppliers = {
            name: SupplierInfo(sku=info["sku"], url=info.get("url"))
            for name, info in d.get("suppliers", {}).items()
        }

        cat_def = categories.get(category)
        reference = cat_def.refdes if cat_def else "U"

        # Normalise protocol-relative datasheet URLs
        datasheet = d.get("datasheet")
        if datasheet and datasheet.startswith("//"):
            datasheet = "https:" + datasheet

        # Fields shared by all tiers; name/value filled after generation
        common = {
            "name": "",
            "value": "",
            "reference": reference,
            "category": category,
            "subcategory": d.get("subcategory"),
            "package": d.get("package") or None,
            "mounting": d.get("mounting"),
            "description": d.get("description", ""),
            "tags": d.get("tags", []),
            "specifications": d.get("specifications"),
            "suppliers": suppliers,
            "symbol": d.get("symbol", ""),
            "footprint": d.get("footprint", ""),
            "keywords": d.get("keywords", []),
            "datasheet": datasheet,
            "notes": d.get("notes"),
        }

        try:
            part = self._build_part(tier, d, common)
        except _ValidationNotice as exc:
            self.notify(str(exc), severity="error")
            return
        except Exception as exc:
            # Escape Rich markup chars in Pydantic validation errors
            msg = str(exc).replace("[", "\\[")
            self.notify(f"Invalid part data: {msg}", severity="error")
            return

        # Generate name, value, description
        part.name = generate_name(part, categories, config.separator)
        part.value = generate_value(part, categories)
        if isinstance(part, JellybeanPart):
            part.description = generate_description(part, categories)

        # Persist
        db = PartsDatabase(library_path / "parts.json")
        db.load()
        try:
            db.add(part)
        except DuplicatePartError:
            self.notify(f"Part already exists: {part.name}", severity="error")
            return

        self.notify(f"Saved: {part.name}")
        form.clear()
        url_input = self.query_one("#url-input", Input)
        url_input.value = ""
        url_input.focus()

    @staticmethod
    def _build_part(
        tier: str,
        d: dict,
        common: dict,
    ) -> ProprietaryPart | SemiJellybeanPart | JellybeanPart:
        """Construct the tier-appropriate Part subclass from form data."""
        if tier == Tier.PROPRIETARY:
            mpn = d.get("mpn", "").strip()
            manufacturer = d.get("manufacturer", "").strip()
            if not mpn:
                raise _ValidationNotice("MPN is required for proprietary parts")
            if not manufacturer:
                raise _ValidationNotice("Manufacturer is required")
            return ProprietaryPart(
                tier=Tier.PROPRIETARY,
                mpn=mpn,
                manufacturer=manufacturer,
                **common,
            )

        if tier == Tier.SEMI_JELLYBEAN:
            mpn = d.get("mpn", "").strip()
            manufacturer = d.get("manufacturer", "").strip()
            base_pn = d.get("base_pn", "").strip()
            if not mpn:
                raise _ValidationNotice("MPN is required")
            if not manufacturer:
                raise _ValidationNotice("Manufacturer is required")
            if not base_pn:
                raise _ValidationNotice("Base PN is required for semi-jellybean parts")
            return SemiJellybeanPart(
                tier=Tier.SEMI_JELLYBEAN,
                mpn=mpn,
                manufacturer=manufacturer,
                base_pn=base_pn,
                **common,
            )

        # Jellybean
        specs = d.get("specifications")
        if not specs:
            raise _ValidationNotice("Specs are required for jellybean parts")
        common["specifications"] = specs
        return JellybeanPart(tier=Tier.JELLYBEAN, **common)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()


class _ValidationNotice(Exception):
    """Internal: carries a user-facing validation message."""
