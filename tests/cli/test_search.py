"""CLI tests for the search command."""

import json

import pytest
from typer.testing import CliRunner

from kist.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


@pytest.fixture
def library(tmp_path, monkeypatch, jellybean_part, proprietary_part):
    """Initialise a library with two parts and chdir into it."""
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    monkeypatch.chdir(tmp_path)

    # Inject parts directly into parts.json
    parts_path = tmp_path / "parts.json"
    data = json.loads(parts_path.read_text())
    data["parts"]["id-1"] = jellybean_part.model_dump(mode="json", exclude_none=True)
    data["parts"]["id-2"] = proprietary_part.model_dump(mode="json", exclude_none=True)
    parts_path.write_text(json.dumps(data, indent=2) + "\n")

    return tmp_path


# --- search ---


def test_search_with_matches(library):
    result = runner.invoke(app, ["search", "10k"])
    assert result.exit_code == 0
    assert "RES-10K-1PCT-0603" in result.output


def test_search_no_matches(library):
    result = runner.invoke(app, ["search", "nonexistent-xyz"])
    assert result.exit_code == 0
    assert "No parts found" in result.output


def test_search_by_description(library):
    result = runner.invoke(app, ["search", "thick film"])
    assert result.exit_code == 0
    assert "RES-10K-1PCT-0603" in result.output


def test_search_by_mpn(library):
    result = runner.invoke(app, ["search", "STM32F405"])
    assert result.exit_code == 0
    assert "IC-STM32F405RGT6-LQFP64" in result.output


def test_search_library_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["search", "anything"])
    assert result.exit_code == 1
    assert "Not a kist library" in result.output
