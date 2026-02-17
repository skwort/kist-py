"""Tests for KiCad preview rendering helpers."""

from __future__ import annotations

from pathlib import Path

from kist.kicad.discovery import KiCadEnvironment
from kist.kicad.render import (
    RenderTheme,
    build_footprint_path_lookup,
    build_symbol_path_lookup,
    get_symbol_units,
    load_footprint,
    render_footprint,
    render_symbol,
)
from kist.kicad.symbols import SymbolLibrary
from kist.models.config import LibraryConfig

FIXTURES = Path(__file__).parents[1] / "fixtures" / "kicad"


def _make_sym_lib_table(config_dir: Path, sym_dir: Path, libraries: list[str]) -> None:
    entries = []
    for name in libraries:
        uri = f"{sym_dir}/{name}.kicad_sym"
        entries.append(
            f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))'
        )
    content = "(sym_lib_table\n  (version 7)\n" + "\n".join(entries) + "\n)\n"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "sym-lib-table").write_text(content)


def _make_fp_lib_table(config_dir: Path, fp_dir: Path, libraries: list[str]) -> None:
    entries = []
    for name in libraries:
        uri = f"{fp_dir}/{name}.pretty"
        entries.append(
            f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))'
        )
    content = "(fp_lib_table\n  (version 7)\n" + "\n".join(entries) + "\n)\n"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "fp-lib-table").write_text(content)


def test_build_symbol_path_lookup_includes_global_and_kist(tmp_path: Path):
    config_dir = tmp_path / "config" / "kicad" / "9.0"
    sym_dir = tmp_path / "data" / "kicad" / "9.0" / "symbols"
    sym_dir.mkdir(parents=True)

    fixture = FIXTURES / "Device_RCL.kicad_sym"
    (sym_dir / "Device_RCL.kicad_sym").write_text(fixture.read_text())
    _make_sym_lib_table(config_dir, sym_dir, ["Device_RCL"])

    kist_root = tmp_path / "kist"
    kist_sym_dir = kist_root / "symbols"
    kist_sym_dir.mkdir(parents=True)
    (kist_sym_dir / "00k-Custom.kicad_sym").write_text(fixture.read_text())

    env = KiCadEnvironment(
        version="9.0",
        config_dir=config_dir,
        data_dir=sym_dir.parent,
        variables={"KICAD9_SYMBOL_DIR": sym_dir},
    )
    lookup = build_symbol_path_lookup(
        env,
        kist_root=kist_root,
        config=LibraryConfig(symbols_dir="symbols"),
    )

    assert lookup["Device_RCL"] == sym_dir / "Device_RCL.kicad_sym"
    assert lookup["00k-Custom"] == kist_sym_dir / "00k-Custom.kicad_sym"


def test_build_footprint_path_lookup_includes_global_and_kist(tmp_path: Path):
    config_dir = tmp_path / "config" / "kicad" / "9.0"
    fp_dir = tmp_path / "data" / "kicad" / "9.0" / "footprints"
    fp_dir.mkdir(parents=True)

    (fp_dir / "Resistor_SMD.pretty").mkdir(parents=True)
    _make_fp_lib_table(config_dir, fp_dir, ["Resistor_SMD"])

    kist_root = tmp_path / "kist"
    kist_fp_dir = kist_root / "footprints"
    (kist_fp_dir / "00k-Custom.pretty").mkdir(parents=True)

    env = KiCadEnvironment(
        version="9.0",
        config_dir=config_dir,
        data_dir=fp_dir.parent,
        variables={"KICAD9_FOOTPRINT_DIR": fp_dir},
    )
    lookup = build_footprint_path_lookup(
        env,
        kist_root=kist_root,
        config=LibraryConfig(footprints_dir="footprints"),
    )

    assert lookup["Resistor_SMD"] == fp_dir / "Resistor_SMD.pretty"
    assert lookup["00k-Custom"] == kist_fp_dir / "00k-Custom.pretty"


def test_render_symbol_and_units():
    lib = SymbolLibrary.load(FIXTURES / "Regulator_Current.kicad_sym")
    sym = lib.get_symbol("HV100K5-G")
    assert sym is not None

    units = get_symbol_units(sym)
    assert units == [1]

    image = render_symbol(sym, unit=1)
    assert image.width > 0
    assert image.height > 0


def test_load_footprint_cache_invalidation(tmp_path: Path):
    fp_path = tmp_path / "Test.kicad_mod"
    fp_path.write_text(
        ' (footprint "X" (layer "F.Cu")\n'
        '  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))\n'
        ")\n"
    )

    tree1 = load_footprint(fp_path)

    fp_path.write_text(
        ' (footprint "X" (layer "F.Cu")\n'
        '  (pad "1" smd rect (at 0 0) (size 2 2) (layers "F.Cu"))\n'
        ")\n"
    )

    tree2 = load_footprint(fp_path)
    assert tree1 != tree2


def test_render_footprint(tmp_path: Path):
    fp_path = tmp_path / "Test.kicad_mod"
    fp_path.write_text(
        ' (footprint "X" (layer "F.Cu")\n'
        '  (fp_line (start -1 -1) (end 1 -1) (layer "F.SilkS") (stroke (width 0.12)))\n'
        '  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))\n'
        ")\n"
    )

    image = render_footprint(load_footprint(fp_path))
    assert image.width > 0
    assert image.height > 0


def test_render_footprint_theme_layer_colors(tmp_path: Path):
    fp_path = tmp_path / "Layered.kicad_mod"
    fp_path.write_text(
        ' (footprint "X" (layer "F.Cu")\n'
        '  (fp_line (start -2 -1) (end -1 -1) (layer "F.SilkS") (stroke (width 0.2)))\n'
        '  (fp_line (start -2 0) (end -1 0) (layer "F.Fab") (stroke (width 0.2)))\n'
        '  (fp_line (start -2 1) (end -1 1) (layer "F.CrtYd") (stroke (width 0.2)))\n'
        '  (fp_line (start 1 -1) (end 2 -1) (layer "F.Cu") (stroke (width 0.2)))\n'
        '  (pad "1" smd rect (at 1 1) (size 0.8 0.8) (layers "F.Cu"))\n'
        ")\n"
    )
    theme = RenderTheme(
        footprint_silk=(10, 20, 30, 255),
        footprint_fab=(40, 50, 60, 255),
        footprint_courtyard=(70, 80, 90, 255),
        footprint_copper=(100, 110, 120, 255),
        footprint_pad=(130, 140, 150, 255),
    )

    image = render_footprint(load_footprint(fp_path), theme=theme, scale_px_per_mm=120)
    if hasattr(image, "get_flattened_data"):
        pixels = set(image.get_flattened_data())
    else:
        pixels = set(image.getdata())

    assert theme.footprint_silk in pixels
    assert theme.footprint_fab in pixels
    assert theme.footprint_courtyard in pixels
    assert theme.footprint_copper in pixels
    assert theme.footprint_pad in pixels
