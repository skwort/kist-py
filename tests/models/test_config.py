"""Tests for configuration models."""

from kist.models import DEFAULT_SUPPLIERS, GlobalConfig, LibraryConfig, ProjectRef

# --- DEFAULT_SUPPLIERS ---


def test_default_suppliers_contents():
    expected = ["digikey", "mouser", "lcsc"]
    assert DEFAULT_SUPPLIERS == expected


# --- LibraryConfig ---


def test_library_config_defaults():
    cfg = LibraryConfig()
    assert cfg.version == 1
    assert cfg.symbols_dir == "symbols"
    assert cfg.footprints_dir == "footprints"
    assert cfg.models_dir == "3dmodels"
    assert cfg.blocks_dir == "blocks"
    assert cfg.suppliers == DEFAULT_SUPPLIERS


def test_library_config_custom_values():
    cfg = LibraryConfig(
        symbols_dir="sym",
        footprints_dir="fp",
        models_dir="models",
        blocks_dir="blk",
        suppliers=["digikey"],
    )
    assert cfg.symbols_dir == "sym"
    assert cfg.footprints_dir == "fp"
    assert cfg.models_dir == "models"
    assert cfg.blocks_dir == "blk"
    assert cfg.suppliers == ["digikey"]


def test_library_config_roundtrip():
    cfg = LibraryConfig(symbols_dir="custom-sym", suppliers=["lcsc", "mouser"])
    data = cfg.model_dump()
    restored = LibraryConfig.model_validate(data)
    assert restored == cfg


# --- GlobalConfig ---


def test_global_config_defaults():
    cfg = GlobalConfig()
    assert cfg.symbols_dir == "symbols"
    assert cfg.footprints_dir == "footprints"
    assert cfg.models_dir == "3dmodels"
    assert cfg.blocks_dir == "blocks"
    assert cfg.suppliers == DEFAULT_SUPPLIERS


def test_global_config_partial_override():
    cfg = GlobalConfig(symbols_dir="my-symbols")
    assert cfg.symbols_dir == "my-symbols"
    # Other fields keep defaults
    assert cfg.footprints_dir == "footprints"
    assert cfg.suppliers == DEFAULT_SUPPLIERS


# --- ProjectRef ---


def test_project_ref_required_library_path():
    ref = ProjectRef(library_path="./lib")
    assert ref.version == 1
    assert ref.library_path == "./lib"


def test_project_ref_roundtrip():
    ref = ProjectRef(library_path="../shared-lib")
    data = ref.model_dump()
    restored = ProjectRef.model_validate(data)
    assert restored == ref
