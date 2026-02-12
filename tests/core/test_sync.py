"""Tests for syncing parts database to .kicad_sym files."""

from pathlib import Path

import pytest

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.database import PartsDatabase, create_empty
from kist.core.sync import sync_symbols
from kist.kicad.mapping import library_filename
from kist.kicad.symbols import SymbolLibrary
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
