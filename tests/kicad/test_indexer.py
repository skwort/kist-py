"""Tests for library index builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from kist.kicad.discovery import KiCadEnvironment
from kist.kicad.indexer import (
    LibraryItem,
    build_footprint_index,
    build_symbol_index,
    load_or_build_index,
)
from kist.models.config import LibraryConfig

FIXTURES = Path(__file__).parents[1] / "fixtures" / "kicad"


# -- Helpers ---


def _make_fp_lib_table(config_dir: Path, fp_dir: Path, libraries: list[str]) -> None:
    """Write an fp-lib-table with entries pointing at *fp_dir*."""
    entries = []
    for name in libraries:
        uri = f"{fp_dir}/{name}.pretty"
        entries.append(
            f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))'
        )
    content = "(fp_lib_table\n  (version 7)\n" + "\n".join(entries) + "\n)\n"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "fp-lib-table").write_text(content)


def _make_sym_lib_table(config_dir: Path, sym_dir: Path, libraries: list[str]) -> None:
    """Write a sym-lib-table with entries pointing at *sym_dir*."""
    entries = []
    for name in libraries:
        uri = f"{sym_dir}/{name}.kicad_sym"
        entries.append(
            f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))'
        )
    content = "(sym_lib_table\n  (version 7)\n" + "\n".join(entries) + "\n)\n"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "sym-lib-table").write_text(content)


def _make_pretty_dir(base: Path, lib_name: str, footprints: list[str]) -> None:
    """Create a .pretty directory with empty .kicad_mod files."""
    pretty = base / f"{lib_name}.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    for fp in footprints:
        (pretty / f"{fp}.kicad_mod").touch()


# -- Fixtures ---


@pytest.fixture()
def kicad_env(tmp_path: Path) -> KiCadEnvironment:
    """Minimal KiCadEnvironment for testing."""
    config_dir = tmp_path / "config" / "kicad" / "9.0"
    data_dir = tmp_path / "data" / "kicad" / "9.0"
    fp_dir = data_dir / "footprints"
    sym_dir = data_dir / "symbols"
    config_dir.mkdir(parents=True)
    fp_dir.mkdir(parents=True)
    sym_dir.mkdir(parents=True)
    return KiCadEnvironment(
        version="9.0",
        config_dir=config_dir,
        data_dir=data_dir,
        variables={
            "KICAD9_FOOTPRINT_DIR": fp_dir,
            "KICAD9_SYMBOL_DIR": sym_dir,
        },
    )


# -- LibraryItem ---


def test_library_item_reference():
    item = LibraryItem(library="Resistor_SMD", name="R_0603_1608Metric", source="kicad")
    assert item.reference == "Resistor_SMD:R_0603_1608Metric"


# -- build_footprint_index ---


def test_footprint_index_from_global_libs(kicad_env: KiCadEnvironment):
    fp_dir = kicad_env.variables["KICAD9_FOOTPRINT_DIR"]
    _make_pretty_dir(fp_dir, "Resistor_SMD", ["R_0603_1608Metric", "R_0805_2012Metric"])
    _make_pretty_dir(fp_dir, "Capacitor_SMD", ["C_0402_1005Metric"])
    _make_fp_lib_table(
        kicad_env.config_dir,
        fp_dir,
        ["Resistor_SMD", "Capacitor_SMD"],
    )

    items = build_footprint_index(kicad_env)
    assert len(items) == 3
    refs = [i.reference for i in items]
    assert "Resistor_SMD:R_0603_1608Metric" in refs
    assert "Resistor_SMD:R_0805_2012Metric" in refs
    assert "Capacitor_SMD:C_0402_1005Metric" in refs
    assert all(i.source == "kicad" for i in items)


def test_footprint_index_empty_when_no_lib_table(kicad_env: KiCadEnvironment):
    items = build_footprint_index(kicad_env)
    assert items == []


def test_footprint_index_includes_kist_footprints(
    kicad_env: KiCadEnvironment, tmp_path: Path
):
    kist_root = tmp_path / "kist-lib"
    fp_dir = kist_root / "footprints"
    _make_pretty_dir(fp_dir, "00k-Resistors", ["R_Custom"])
    config = LibraryConfig(footprints_dir="footprints")

    items = build_footprint_index(kicad_env, kist_root=kist_root, config=config)
    assert len(items) == 1
    assert items[0].reference == "00k-Resistors:R_Custom"
    assert items[0].source == "kist"


def test_footprint_index_skips_missing_dirs(kicad_env: KiCadEnvironment):
    """Libraries in the table whose dirs don't exist are silently skipped."""
    fp_dir = kicad_env.variables["KICAD9_FOOTPRINT_DIR"]
    _make_fp_lib_table(kicad_env.config_dir, fp_dir, ["Missing_Lib"])
    items = build_footprint_index(kicad_env)
    assert items == []


# -- build_symbol_index ---


def test_symbol_index_from_global_libs(kicad_env: KiCadEnvironment):
    """Index symbols from a real fixture file via the sym-lib-table."""
    sym_dir = kicad_env.variables["KICAD9_SYMBOL_DIR"]

    # Copy fixture file into the test sym dir
    fixture = FIXTURES / "Device_RCL.kicad_sym"
    (sym_dir / "Device_RCL.kicad_sym").write_text(fixture.read_text())

    _make_sym_lib_table(kicad_env.config_dir, sym_dir, ["Device_RCL"])

    items = build_symbol_index(kicad_env)
    refs = [i.reference for i in items]
    assert "Device_RCL:C" in refs
    assert "Device_RCL:L" in refs
    assert "Device_RCL:R" in refs
    assert all(i.source == "kicad" for i in items)


def test_symbol_index_empty_when_no_lib_table(kicad_env: KiCadEnvironment):
    items = build_symbol_index(kicad_env)
    assert items == []


def test_symbol_index_includes_kist_symbols(
    kicad_env: KiCadEnvironment, tmp_path: Path
):
    kist_root = tmp_path / "kist-lib"
    sym_dir = kist_root / "symbols"
    sym_dir.mkdir(parents=True)

    # Copy fixture as a kist symbol library
    fixture = FIXTURES / "Device_RCL.kicad_sym"
    (sym_dir / "00k-Passives.kicad_sym").write_text(fixture.read_text())

    config = LibraryConfig(symbols_dir="symbols")

    items = build_symbol_index(kicad_env, kist_root=kist_root, config=config)
    assert len(items) == 3
    assert all(i.source == "kist" for i in items)
    assert all(i.library == "00k-Passives" for i in items)


def test_symbol_index_skips_unparseable_files(kicad_env: KiCadEnvironment):
    """Corrupted symbol files are logged and skipped, not fatal."""
    sym_dir = kicad_env.variables["KICAD9_SYMBOL_DIR"]
    (sym_dir / "bad.kicad_sym").write_text("not valid sexpr content {{{}}")
    _make_sym_lib_table(kicad_env.config_dir, sym_dir, ["bad"])

    items = build_symbol_index(kicad_env)
    assert items == []


# -- load_or_build_index ---


def test_load_or_build_creates_cache(kicad_env: KiCadEnvironment, tmp_path: Path):
    fp_dir = kicad_env.variables["KICAD9_FOOTPRINT_DIR"]
    _make_pretty_dir(fp_dir, "Test_Lib", ["FP_A"])
    _make_fp_lib_table(kicad_env.config_dir, fp_dir, ["Test_Lib"])

    cache_dir = tmp_path / "cache"
    index = load_or_build_index(kicad_env, cache_dir=cache_dir)

    assert len(index.footprints) == 1
    assert index.footprints[0].reference == "Test_Lib:FP_A"

    # Cache file should exist
    cache_files = list(cache_dir.glob("library_index_*.json"))
    assert len(cache_files) == 1


def test_load_or_build_uses_cache(kicad_env: KiCadEnvironment, tmp_path: Path):
    fp_dir = kicad_env.variables["KICAD9_FOOTPRINT_DIR"]
    _make_pretty_dir(fp_dir, "Test_Lib", ["FP_A"])
    _make_fp_lib_table(kicad_env.config_dir, fp_dir, ["Test_Lib"])

    cache_dir = tmp_path / "cache"

    # Build first time
    index1 = load_or_build_index(kicad_env, cache_dir=cache_dir)
    assert len(index1.footprints) == 1

    # Add another footprint file (but don't update lib table mtime)
    (fp_dir / "Test_Lib.pretty" / "FP_B.kicad_mod").touch()

    # Second call should return cached version (still 1 footprint)
    index2 = load_or_build_index(kicad_env, cache_dir=cache_dir)
    assert len(index2.footprints) == 1


def test_load_or_build_both_types(kicad_env: KiCadEnvironment, tmp_path: Path):
    fp_dir = kicad_env.variables["KICAD9_FOOTPRINT_DIR"]
    sym_dir = kicad_env.variables["KICAD9_SYMBOL_DIR"]

    _make_pretty_dir(fp_dir, "Resistor_SMD", ["R_0603"])
    _make_fp_lib_table(kicad_env.config_dir, fp_dir, ["Resistor_SMD"])

    fixture = FIXTURES / "Device_RCL.kicad_sym"
    (sym_dir / "Device_RCL.kicad_sym").write_text(fixture.read_text())
    _make_sym_lib_table(kicad_env.config_dir, sym_dir, ["Device_RCL"])

    cache_dir = tmp_path / "cache"
    index = load_or_build_index(kicad_env, cache_dir=cache_dir)

    assert len(index.footprints) == 1
    assert len(index.symbols) == 3
