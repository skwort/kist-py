"""Tests for configuration I/O and resolution."""

import pytest

from kist.core.config import (
    load_global_config,
    load_library_config,
    load_project_ref,
    resolve_init_config,
    save_library_config,
    save_project_ref,
)
from kist.errors import ConfigError
from kist.models import DEFAULT_SUPPLIERS, LibraryConfig, ProjectRef


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    """Point global config at an empty temp directory for every test."""
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


# --- load_global_config ---


def test_load_global_config_missing_file_returns_defaults():
    cfg = load_global_config()
    assert cfg.symbols_dir == "symbols"
    assert cfg.suppliers == DEFAULT_SUPPLIERS


def test_load_global_config_partial_toml(tmp_path, monkeypatch):
    config_dir = tmp_path / "global"
    config_dir.mkdir()
    monkeypatch.setenv("KIST_CONFIG_DIR", str(config_dir))
    (config_dir / "config.toml").write_text('symbols_dir = "sym"\n')
    cfg = load_global_config()
    assert cfg.symbols_dir == "sym"
    assert cfg.footprints_dir == "footprints"  # default preserved


def test_load_global_config_invalid_toml(tmp_path, monkeypatch):
    config_dir = tmp_path / "global"
    config_dir.mkdir()
    monkeypatch.setenv("KIST_CONFIG_DIR", str(config_dir))
    (config_dir / "config.toml").write_text("not valid toml [[[")
    with pytest.raises(ConfigError):
        load_global_config()


# --- resolve_init_config ---


def test_resolve_defaults_only():
    cfg = resolve_init_config()
    assert cfg.version == 1
    assert cfg.symbols_dir == "symbols"
    assert cfg.suppliers == DEFAULT_SUPPLIERS


def test_resolve_global_merge(tmp_path, monkeypatch):
    config_dir = tmp_path / "global"
    config_dir.mkdir()
    monkeypatch.setenv("KIST_CONFIG_DIR", str(config_dir))
    (config_dir / "config.toml").write_text(
        'footprints_dir = "fp"\nsuppliers = ["digikey"]\n'
    )
    cfg = resolve_init_config()
    assert cfg.footprints_dir == "fp"
    assert cfg.suppliers == ["digikey"]
    assert cfg.symbols_dir == "symbols"  # built-in default


def test_resolve_cli_overrides():
    cfg = resolve_init_config(symbols_dir="my-sym", blocks_dir="my-blk")
    assert cfg.symbols_dir == "my-sym"
    assert cfg.blocks_dir == "my-blk"
    assert cfg.footprints_dir == "footprints"


def test_resolve_none_filtering():
    """None values from absent CLI flags are ignored."""
    cfg = resolve_init_config(symbols_dir=None, footprints_dir="fp")
    assert cfg.symbols_dir == "symbols"
    assert cfg.footprints_dir == "fp"


# --- save/load library config ---


def test_library_config_roundtrip(tmp_path):
    cfg = LibraryConfig(symbols_dir="sym", suppliers=["lcsc"])
    save_library_config(tmp_path, cfg)
    loaded = load_library_config(tmp_path)
    assert loaded == cfg


def test_library_config_categories_roundtrip(tmp_path):
    """CategoryDef nested structures survive tomlkit serialization."""
    from kist.core.categories import WELL_KNOWN_CATEGORIES

    cfg = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))
    save_library_config(tmp_path, cfg)
    loaded = load_library_config(tmp_path)

    assert set(loaded.categories.keys()) == set(cfg.categories.keys())
    # Spot-check a category with subcategory overrides
    cap = loaded.categories["CAP"]
    assert cap.name == "Capacitors"
    assert cap.refdes == "C"
    assert "CER" in cap.subcategory_key_specs
    assert "dielectric" in cap.subcategory_key_specs["CER"]
    assert cap.subcategory_names["CER"] == "Ceramic"
    assert cap.value_field == "capacitance"
    assert cap.symbol_template == "capacitor"


def test_library_config_creates_kist_dir(tmp_path):
    save_library_config(tmp_path, LibraryConfig())
    assert (tmp_path / ".kist").is_dir()
    assert (tmp_path / ".kist" / "config.toml").exists()


def test_load_library_config_missing_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_library_config(tmp_path)


def test_load_library_config_invalid_raises(tmp_path):
    kist_dir = tmp_path / ".kist"
    kist_dir.mkdir()
    (kist_dir / "config.toml").write_text("bad toml [[[")
    with pytest.raises(ConfigError):
        load_library_config(tmp_path)


# --- save/load project ref ---


def test_project_ref_roundtrip(tmp_path):
    ref = ProjectRef(library_path="../lib")
    path = tmp_path / "kist.toml"
    save_project_ref(path, ref)
    loaded = load_project_ref(path)
    assert loaded == ref


def test_project_ref_toml_content(tmp_path):
    ref = ProjectRef(library_path="./lib")
    path = tmp_path / "kist.toml"
    save_project_ref(path, ref)
    content = path.read_text()
    assert "version = 1" in content
    assert 'library_path = "./lib"' in content


def test_load_project_ref_missing_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_project_ref(tmp_path / "kist.toml")


def test_load_project_ref_invalid_raises(tmp_path):
    path = tmp_path / "kist.toml"
    path.write_text("bad [[[")
    with pytest.raises(ConfigError):
        load_project_ref(path)
