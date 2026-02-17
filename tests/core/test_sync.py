"""Tests for syncing parts database to .kicad_sym files."""

from pathlib import Path

import pytest

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.database import PartsDatabase, create_empty
from kist.core.sync import SYM_LIB_TABLE, sync_sym_lib_table, sync_symbols
from kist.kicad.mapping import library_filename
from kist.kicad.symbols import SymbolLibrary
from kist.kicad.templates import spec_property_key, stub_symbol
from kist.models import (
    JellybeanPart,
    LibraryConfig,
    Mounting,
    ProprietaryPart,
    Tier,
)

CATS = WELL_KNOWN_CATEGORIES


def _config_with_categories() -> LibraryConfig:
    return LibraryConfig(categories=dict(CATS))


# --- fixtures and factories ---


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, PartsDatabase, LibraryConfig]:
    """A minimal library directory with empty database and default config."""
    root = tmp_path / "lib"
    root.mkdir()
    (root / "symbols").mkdir()
    db_path = root / "parts.json"
    create_empty(db_path)
    db = PartsDatabase(db_path)
    db.load()
    config = _config_with_categories()
    return root, db, config


def _make_resistor(resistance: str, tolerance: str, package: str) -> JellybeanPart:
    name = f"RES-TEST-{package}"
    return JellybeanPart(
        name=name,
        tier=Tier.JELLYBEAN,
        description=f"{resistance} {tolerance} {package} resistor",
        category="RES",
        package=package,
        mounting=Mounting.SMD,
        symbol=f"00k-Resistors:{name}",
        footprint=f"Resistor_SMD:R_{package}",
        value="10K",
        reference="R",
        specifications={"resistance": resistance, "tolerance": tolerance},
    )


def _make_capacitor(capacitance: str, voltage: str, package: str) -> JellybeanPart:
    name = f"CAP-TEST-{package}"
    return JellybeanPart(
        name=name,
        tier=Tier.JELLYBEAN,
        description=f"{capacitance} {voltage} {package} capacitor",
        category="CAP",
        package=package,
        mounting=Mounting.SMD,
        symbol=f"00k-Capacitors:{name}",
        footprint=f"Capacitor_SMD:C_{package}",
        value="100n",
        reference="C",
        specifications={"capacitance": capacitance, "voltage_rating": voltage},
    )


def _res_filename() -> str:
    return library_filename(CATS["RES"].name)


def _cap_filename() -> str:
    return library_filename(CATS["CAP"].name)


def _ic_filename() -> str:
    return library_filename(CATS["IC"].name)


# --- sync_symbols ---


def test_empty_database_produces_no_files(library):
    root, db, config = library
    sync_symbols(root, db, config)
    sym_dir = root / "symbols"
    assert list(sym_dir.glob("*.kicad_sym")) == []


def test_one_resistor_creates_symbol_file(library):
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603")
    db.add(part)

    sync_symbols(root, db, config)

    path = root / "symbols" / _res_filename()
    assert path.exists()
    lib = SymbolLibrary.load(path)
    assert part.name in lib.symbols()


def test_multiple_categories_create_multiple_files(library):
    root, db, config = library
    res = _make_resistor("10kΩ", "1%", "0603")
    cap = _make_capacitor("100nF", "50V", "0402")
    db.add(res)
    db.add(cap)

    sync_symbols(root, db, config)

    res_path = root / "symbols" / _res_filename()
    cap_path = root / "symbols" / _cap_filename()
    assert res_path.exists()
    assert cap_path.exists()

    res_lib = SymbolLibrary.load(res_path)
    assert res.name in res_lib.symbols()

    cap_lib = SymbolLibrary.load(cap_path)
    assert cap.name in cap_lib.symbols()


# --- idempotency and updates ---


def test_sync_is_idempotent(library):
    root, db, config = library
    part = _make_resistor("4.7kΩ", "5%", "0805")
    db.add(part)

    sync_symbols(root, db, config)
    path = root / "symbols" / _res_filename()
    first_content = path.read_text()

    sync_symbols(root, db, config)
    second_content = path.read_text()

    assert first_content == second_content


def test_updated_part_reflected_after_resync(library):
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603")
    ipn = db.add(part)

    sync_symbols(root, db, config)

    # Update description by replacing the part
    updated = part.model_copy(update={"description": "Updated description"})
    db._parts[ipn] = updated
    db.save()

    sync_symbols(root, db, config)

    path = root / "symbols" / _res_filename()
    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    assert sym is not None
    # Check the Description property was updated
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == "Description"
        ):
            assert child[2] == "Updated description"
            break


# --- spec properties ---


def test_sync_writes_spec_properties(library):
    """Synced resistor symbols include specification properties."""
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603")
    db.add(part)

    sync_symbols(root, db, config)

    path = root / "symbols" / _res_filename()
    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    # Find the resistance property
    res_prop = _find_prop(sym, "resistance")
    assert res_prop is not None
    assert str(res_prop[2]) == "10kΩ"
    tol_prop = _find_prop(sym, "tolerance")
    assert tol_prop is not None
    assert str(tol_prop[2]) == "1%"


def test_sync_preserves_visible_spec_properties(library):
    """If a user makes a spec property visible, re-sync preserves that."""
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603")
    db.add(part)

    # First sync -- all specs hidden
    sync_symbols(root, db, config)

    # Simulate user toggling "resistance" to visible in KiCad:
    # remove (hide yes) from the resistance property's effects
    path = root / "symbols" / _res_filename()
    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    res_prop = _find_prop(sym, "resistance")
    assert res_prop is not None
    _make_prop_visible(res_prop)
    lib.save(path)

    # Re-sync -- should preserve visibility
    sync_symbols(root, db, config)

    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    res_prop = _find_prop(sym, "resistance")
    assert res_prop is not None
    assert not _prop_is_hidden(res_prop), "resistance should stay visible after re-sync"

    # tolerance should still be hidden
    tol_prop = _find_prop(sym, "tolerance")
    assert tol_prop is not None
    assert _prop_is_hidden(tol_prop)


def test_sync_passes_only_spec_visibility_to_symbol_builder(library, monkeypatch):
    """Visibility carryover should include only this part's spec properties."""
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603")
    db.add(part)
    sync_symbols(root, db, config)  # create existing symbol

    captured: dict[str, set[str] | None] = {}

    def fake_visible(_sym):
        return {"Reference", "resistance", "not_a_spec"}

    def fake_symbol_for_part(part_arg, categories_arg, *, visible_specs=None):
        captured["visible_specs"] = visible_specs
        return stub_symbol(part_arg.name, {"Reference": "R", "Value": "X"})

    monkeypatch.setattr("kist.core.sync.get_visible_properties", fake_visible)
    monkeypatch.setattr("kist.core.sync.symbol_for_part", fake_symbol_for_part)

    sync_symbols(root, db, config)

    assert captured["visible_specs"] == {"resistance"}


def test_sync_preserves_visible_colliding_spec_property(library):
    """Visibility preservation also works for renamed colliding spec keys."""
    root, db, config = library
    part = _make_resistor("10kΩ", "1%", "0603").model_copy(
        update={"specifications": {"Value": "from-spec", "tolerance": "1%"}}
    )
    db.add(part)
    sync_symbols(root, db, config)

    path = root / "symbols" / _res_filename()
    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    value_spec_key = spec_property_key("Value")
    value_spec_prop = _find_prop(sym, value_spec_key)
    assert value_spec_prop is not None
    _make_prop_visible(value_spec_prop)
    lib.save(path)

    sync_symbols(root, db, config)

    lib = SymbolLibrary.load(path)
    sym = lib.get_symbol(part.name)
    value_spec_prop = _find_prop(sym, value_spec_key)
    assert value_spec_prop is not None
    assert not _prop_is_hidden(value_spec_prop)


def _find_prop(sym, key):
    for child in sym:
        if (
            isinstance(child, list)
            and child
            and child[0] == "property"
            and len(child) > 2
            and child[1] == key
        ):
            return child
    return None


def _prop_is_hidden(prop):
    from kist.sexpr import find_one

    effects = find_one(prop, "effects")
    if effects is None:
        return False
    hide = find_one(effects, "hide")
    return hide is not None and len(hide) > 1 and str(hide[1]) == "yes"


def _make_prop_visible(prop):
    """Remove (hide yes) from a property's effects."""
    from kist.sexpr import find_one

    effects = find_one(prop, "effects")
    if effects is None:
        return
    effects[:] = [
        child
        for child in effects
        if not (isinstance(child, list) and child and child[0] == "hide")
    ]


# --- edge cases ---


def test_proprietary_part_creates_stub_symbol(library):
    root, db, config = library
    part = ProprietaryPart(
        name="IC-STM32F405-LQFP64",
        tier=Tier.PROPRIETARY,
        description="ARM Cortex-M4 MCU",
        category="IC",
        package="LQFP-64",
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        symbol="00k-ICs:IC-STM32F405-LQFP64",
        footprint="Package_QFP:LQFP-64_10x10mm_P0.5mm",
        value="STM32F405RGT6",
        reference="U",
    )
    db.add(part)

    sync_symbols(root, db, config)

    path = root / "symbols" / _ic_filename()
    assert path.exists()
    lib = SymbolLibrary.load(path)
    assert part.name in lib.symbols()


def test_creates_symbols_dir_if_missing(tmp_path):
    root = tmp_path / "lib"
    root.mkdir()
    # No symbols/ dir created
    db_path = root / "parts.json"
    create_empty(db_path)
    db = PartsDatabase(db_path)
    db.load()
    config = _config_with_categories()

    part = _make_resistor("1kΩ", "5%", "0402")
    db.add(part)

    sync_symbols(root, db, config)

    path = root / "symbols" / _res_filename()
    assert path.exists()


def test_sync_symbols_returns_written_files(library):
    root, db, config = library
    res = _make_resistor("10kΩ", "1%", "0603")
    cap = _make_capacitor("100nF", "50V", "0402")
    db.add(res)
    db.add(cap)

    written = sync_symbols(root, db, config)
    assert len(written) == 2
    assert all(p.suffix == ".kicad_sym" for p in written)


# --- sync_sym_lib_table ---


def test_sync_sym_lib_table_creates_file(library):
    root, db, config = library
    db.add(_make_resistor("10kΩ", "1%", "0603"))
    symbol_files = sync_symbols(root, db, config)

    project_dir = root.parent
    sync_sym_lib_table(project_dir, symbol_files, config)

    table_path = project_dir / SYM_LIB_TABLE
    assert table_path.exists()
    content = table_path.read_text()
    assert "00k-Resistors" in content
    assert "${KIPRJMOD}/lib/symbols/" in content


def test_sync_sym_lib_table_updates_existing(library):
    root, db, config = library
    project_dir = root.parent

    # Write an existing table with a non-kist entry
    existing = (
        "(sym_lib_table\n"
        "  (version 7)\n"
        '  (lib (name "power")(type "KiCad")'
        '(uri "${KICAD8_SYMBOL_DIR}/power.kicad_sym")'
        '(options "")(descr ""))\n'
        ")\n"
    )
    (project_dir / SYM_LIB_TABLE).write_text(existing)

    db.add(_make_resistor("10kΩ", "1%", "0603"))
    symbol_files = sync_symbols(root, db, config)
    sync_sym_lib_table(project_dir, symbol_files, config)

    content = (project_dir / SYM_LIB_TABLE).read_text()
    # Non-kist entry preserved
    assert "power" in content
    # Kist entry added
    assert "00k-Resistors" in content


def test_sync_sym_lib_table_empty_db(library):
    root, db, config = library
    symbol_files = sync_symbols(root, db, config)

    project_dir = root.parent
    sync_sym_lib_table(project_dir, symbol_files, config)

    table_path = project_dir / SYM_LIB_TABLE
    assert table_path.exists()
    content = table_path.read_text()
    assert "sym_lib_table" in content
    # No lib entries
    assert "00k-" not in content


def test_sync_sym_lib_table_idempotent(library):
    root, db, config = library
    db.add(_make_resistor("10kΩ", "1%", "0603"))
    symbol_files = sync_symbols(root, db, config)

    project_dir = root.parent
    sync_sym_lib_table(project_dir, symbol_files, config)
    first = (project_dir / SYM_LIB_TABLE).read_text()

    sync_sym_lib_table(project_dir, symbol_files, config)
    second = (project_dir / SYM_LIB_TABLE).read_text()

    assert first == second
