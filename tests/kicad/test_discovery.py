"""Tests for KiCad installation discovery and lib-table parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from kist.kicad.discovery import (
    KiCadEnvironment,
    LibTableEntry,
    _nix_kicad_variables,
    detect_kicad,
    parse_lib_table,
    resolve_uri,
)

# -- Fixtures ---


@pytest.fixture()
def kicad_env(tmp_path: Path) -> KiCadEnvironment:
    """A minimal KiCadEnvironment pointing at tmp_path."""
    return KiCadEnvironment(
        version="9.0",
        config_dir=tmp_path / "config" / "kicad" / "9.0",
        data_dir=tmp_path / "data" / "kicad" / "9.0",
        variables={
            "KICAD9_FOOTPRINT_DIR": tmp_path / "data" / "kicad" / "9.0" / "footprints",
            "KICAD9_SYMBOL_DIR": tmp_path / "data" / "kicad" / "9.0" / "symbols",
            "KICAD9_3DMODEL_DIR": tmp_path / "data" / "kicad" / "9.0" / "3dmodels",
        },
    )


FP_LIB_TABLE = """\
(fp_lib_table
  (version 7)
  (lib (name "Resistor_SMD")(type "KiCad")(uri "${KICAD9_FOOTPRINT_DIR}/Resistor_SMD.pretty")(options "")(descr ""))
  (lib (name "Capacitor_SMD")(type "KiCad")(uri "${KICAD9_FOOTPRINT_DIR}/Capacitor_SMD.pretty")(options "")(descr ""))
)
"""

SYM_LIB_TABLE = """\
(sym_lib_table
  (version 7)
  (lib (name "Device")(type "KiCad")(uri "${KICAD9_SYMBOL_DIR}/Device.kicad_sym")(options "")(descr ""))
  (lib (name "power")(type "KiCad")(uri "${KICAD9_SYMBOL_DIR}/power.kicad_sym")(options "")(descr ""))
)
"""


# -- resolve_uri ---


def test_resolve_uri_substitutes_variable(kicad_env: KiCadEnvironment):
    uri = "${KICAD9_FOOTPRINT_DIR}/Resistor_SMD.pretty"
    result = resolve_uri(uri, kicad_env)
    expected = kicad_env.variables["KICAD9_FOOTPRINT_DIR"] / "Resistor_SMD.pretty"
    assert result == expected


def test_resolve_uri_leaves_unknown_variable(kicad_env: KiCadEnvironment):
    uri = "${UNKNOWN_VAR}/something"
    result = resolve_uri(uri, kicad_env)
    assert "${UNKNOWN_VAR}" in str(result)


def test_resolve_uri_no_variables(kicad_env: KiCadEnvironment):
    uri = "/absolute/path/to/lib.pretty"
    result = resolve_uri(uri, kicad_env)
    assert result == Path("/absolute/path/to/lib.pretty")


def test_resolve_uri_multiple_variables(kicad_env: KiCadEnvironment):
    uri = "${KICAD9_FOOTPRINT_DIR}/${KICAD9_SYMBOL_DIR}/mixed"
    result = resolve_uri(uri, kicad_env)
    # Both variables should be resolved
    assert "${KICAD9_FOOTPRINT_DIR}" not in str(result)
    assert "${KICAD9_SYMBOL_DIR}" not in str(result)
    assert str(result).endswith("/mixed")


# -- parse_lib_table ---


def test_parse_fp_lib_table(tmp_path: Path):
    table_path = tmp_path / "fp-lib-table"
    table_path.write_text(FP_LIB_TABLE)

    entries = parse_lib_table(table_path)
    assert len(entries) == 2
    assert entries[0] == LibTableEntry(
        name="Resistor_SMD",
        uri="${KICAD9_FOOTPRINT_DIR}/Resistor_SMD.pretty",
        lib_type="KiCad",
    )
    assert entries[1].name == "Capacitor_SMD"


def test_parse_sym_lib_table(tmp_path: Path):
    table_path = tmp_path / "sym-lib-table"
    table_path.write_text(SYM_LIB_TABLE)

    entries = parse_lib_table(table_path)
    assert len(entries) == 2
    assert entries[0].name == "Device"
    assert entries[1].name == "power"
    assert "${KICAD9_SYMBOL_DIR}" in entries[0].uri


def test_parse_lib_table_missing_file(tmp_path: Path):
    missing = tmp_path / "nonexistent"
    assert parse_lib_table(missing) == []


def test_parse_lib_table_empty(tmp_path: Path):
    table_path = tmp_path / "fp-lib-table"
    table_path.write_text("(fp_lib_table\n  (version 7)\n)\n")
    entries = parse_lib_table(table_path)
    assert entries == []


# -- detect_kicad ---


def test_detect_kicad_finds_highest_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """detect_kicad picks the highest versioned subdir."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"

    # Create two version dirs
    (config_base / "8.0").mkdir(parents=True)
    (config_base / "9.0").mkdir(parents=True)

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(config_base))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(data_base))

    env = detect_kicad()
    assert env is not None
    assert env.version == "9.0"
    assert env.config_dir == config_base / "9.0"
    assert env.data_dir == data_base / "9.0"


def test_detect_kicad_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """detect_kicad returns None when no KiCad config dir exists."""
    empty = tmp_path / "empty"
    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(empty))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(empty))

    assert detect_kicad() is None


def test_detect_kicad_builds_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """detect_kicad populates the variable map."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"
    (config_base / "9.0").mkdir(parents=True)

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(config_base))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(data_base))
    # Disable Nix detection (test dirs are empty, would trigger fallback)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    # Clear any real env vars that might interfere
    monkeypatch.delenv("KICAD9_FOOTPRINT_DIR", raising=False)
    monkeypatch.delenv("KICAD9_SYMBOL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_3DMODEL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_TEMPLATE_DIR", raising=False)

    env = detect_kicad()
    assert env is not None
    assert "KICAD9_FOOTPRINT_DIR" in env.variables
    assert env.variables["KICAD9_FOOTPRINT_DIR"] == data_base / "9.0" / "footprints"
    assert env.variables["KICAD9_SYMBOL_DIR"] == data_base / "9.0" / "symbols"


def test_detect_kicad_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Environment variables override default data paths."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"
    custom_fp = tmp_path / "custom" / "footprints"
    custom_fp.mkdir(parents=True)
    (custom_fp / "dummy.pretty").mkdir()  # non-empty so Nix fallback won't trigger

    (config_base / "9.0").mkdir(parents=True)

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(config_base))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(data_base))
    monkeypatch.setenv("KICAD9_FOOTPRINT_DIR", str(custom_fp))
    # Disable Nix detection for the remaining vars
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    # Clear others
    monkeypatch.delenv("KICAD9_SYMBOL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_3DMODEL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_TEMPLATE_DIR", raising=False)

    env = detect_kicad()
    assert env is not None
    assert env.variables["KICAD9_FOOTPRINT_DIR"] == custom_fp


def test_detect_kicad_ignores_non_version_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Non-version directories like 'scripting' are ignored."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"

    (config_base / "scripting").mkdir(parents=True)
    (config_base / "8.0").mkdir(parents=True)

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(config_base))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(data_base))

    env = detect_kicad()
    assert env is not None
    assert env.version == "8.0"


# -- Nix detection ---


def test_nix_kicad_variables_parses_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """_nix_kicad_variables extracts paths from a Nix-style wrapper script."""
    nix_fp = tmp_path / "nix-fps"
    nix_sym = tmp_path / "nix-syms"
    nix_fp.mkdir()
    nix_sym.mkdir()
    # Dirs must have content for is_dir() validation in _nix_kicad_variables
    (nix_fp / "Resistor.pretty").mkdir()
    (nix_sym / "Device.kicad_sym").touch()

    # Write a Nix-style wrapper at a path under /nix/store/
    nix_bin = tmp_path / "nix" / "store" / "abc" / "bin" / "kicad"
    nix_bin.parent.mkdir(parents=True)
    nix_bin.write_text(
        f"#!/nix/store/bash/bin/bash -e\n"
        f"export KICAD9_FOOTPRINT_DIR=${{KICAD9_FOOTPRINT_DIR-'{nix_fp}'}}\n"
        f"export KICAD9_SYMBOL_DIR=${{KICAD9_SYMBOL_DIR-'{nix_sym}'}}\n"
    )

    monkeypatch.setattr("shutil.which", lambda cmd: str(nix_bin))

    result = _nix_kicad_variables()
    assert result["KICAD9_FOOTPRINT_DIR"] == nix_fp
    assert result["KICAD9_SYMBOL_DIR"] == nix_sym


def test_nix_kicad_variables_returns_empty_for_non_nix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Non-Nix kicad binary returns empty dict."""
    wrapper = tmp_path / "usr" / "bin" / "kicad"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nexec /usr/lib/kicad/bin/kicad\n")

    monkeypatch.setattr("shutil.which", lambda cmd: str(wrapper))

    result = _nix_kicad_variables()
    assert result == {}


def test_nix_kicad_variables_returns_empty_when_not_found(
    monkeypatch: pytest.MonkeyPatch,
):
    """No kicad binary returns empty dict."""
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    assert _nix_kicad_variables() == {}


def test_nix_fallback_overrides_empty_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When default dirs are empty, Nix paths are used instead."""
    config_base = tmp_path / "config"
    data_base = tmp_path / "data"
    (config_base / "9.0").mkdir(parents=True)
    # Create empty default dirs (as KiCad does on Nix)
    (data_base / "9.0" / "footprints").mkdir(parents=True)
    (data_base / "9.0" / "symbols").mkdir(parents=True)

    nix_fp = tmp_path / "nix-fps"
    nix_sym = tmp_path / "nix-syms"
    nix_fp.mkdir()
    nix_sym.mkdir()
    # Put content in Nix dirs
    (nix_fp / "Resistor.pretty").mkdir()
    (nix_sym / "Device.kicad_sym").touch()

    nix_bin = tmp_path / "nix" / "store" / "abc" / "bin" / "kicad"
    nix_bin.parent.mkdir(parents=True)
    nix_bin.write_text(
        f"#!/nix/store/bash/bin/bash -e\n"
        f"export KICAD9_FOOTPRINT_DIR=${{KICAD9_FOOTPRINT_DIR-'{nix_fp}'}}\n"
        f"export KICAD9_SYMBOL_DIR=${{KICAD9_SYMBOL_DIR-'{nix_sym}'}}\n"
    )

    monkeypatch.setattr("platformdirs.user_config_dir", lambda app: str(config_base))
    monkeypatch.setattr("platformdirs.user_data_dir", lambda app: str(data_base))
    monkeypatch.setattr("shutil.which", lambda cmd: str(nix_bin))
    monkeypatch.delenv("KICAD9_FOOTPRINT_DIR", raising=False)
    monkeypatch.delenv("KICAD9_SYMBOL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_3DMODEL_DIR", raising=False)
    monkeypatch.delenv("KICAD9_TEMPLATE_DIR", raising=False)

    env = detect_kicad()
    assert env is not None
    assert env.variables["KICAD9_FOOTPRINT_DIR"] == nix_fp
    assert env.variables["KICAD9_SYMBOL_DIR"] == nix_sym
