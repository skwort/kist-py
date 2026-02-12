"""CLI tests for the check command."""

import json

import pytest
from typer.testing import CliRunner

from kist.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


def _init_library_with_parts(tmp_path, monkeypatch, parts: list[dict]):
    """Initialise a library and inject parts."""
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    monkeypatch.chdir(tmp_path)

    parts_path = tmp_path / "parts.json"
    data = json.loads(parts_path.read_text())
    for i, part in enumerate(parts):
        data["parts"][f"id-{i}"] = part
    parts_path.write_text(json.dumps(data, indent=2) + "\n")


# --- check: all clean ---


def test_check_all_clean(tmp_path, monkeypatch, jellybean_part):
    _init_library_with_parts(
        tmp_path,
        monkeypatch,
        [
            jellybean_part.model_dump(mode="json", exclude_none=True),
        ],
    )
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "All clean" in result.output


def test_check_empty_database(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "No parts to check" in result.output


# --- check: name mismatch ---


def test_check_name_mismatch(tmp_path, monkeypatch, jellybean_part):
    part_data = jellybean_part.model_dump(mode="json", exclude_none=True)
    part_data["name"] = "WRONG-NAME"

    _init_library_with_parts(tmp_path, monkeypatch, [part_data])

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "Name mismatch" in result.output
    assert "WRONG-NAME" in result.output


# --- check: duplicate identity ---


def test_check_duplicate_identity(tmp_path, monkeypatch, jellybean_part):
    part_a = jellybean_part.model_dump(mode="json", exclude_none=True)
    part_b = jellybean_part.model_dump(mode="json", exclude_none=True)
    # Same specs but different names -- identity collision
    part_b["name"] = "RES-10K-1PCT-0603-COPY"

    _init_library_with_parts(tmp_path, monkeypatch, [part_a, part_b])

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "Duplicate identity" in result.output


# --- check: library not found ---


def test_check_library_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "Not a kist library" in result.output
