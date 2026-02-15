"""CLI integration tests for init and link commands."""

import pytest
from typer.testing import CliRunner

from kist.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


# --- kist init ---


def test_init_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Initialised" in result.output
    assert (tmp_path / ".kist" / "config.toml").exists()


def test_init_with_path(tmp_path):
    target = tmp_path / "mylib"
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 0
    assert (target / ".kist" / "config.toml").exists()


def test_init_with_dir_overrides(tmp_path):
    result = runner.invoke(
        app,
        ["init", "--path", str(tmp_path), "--symbols-dir", "sym", "--blocks-dir", "b"],
    )
    assert result.exit_code == 0
    assert (tmp_path / "sym").is_dir()
    assert (tmp_path / "b").is_dir()


def test_init_seeds_categories(tmp_path):
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    content = (tmp_path / ".kist" / "config.toml").read_text()
    assert "[categories.RES]" in content
    assert "[categories.CAP]" in content
    assert 'library_prefix = "00k"' in content


def test_init_already_initialised(tmp_path):
    runner.invoke(app, ["init", "--path", str(tmp_path)])
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Already initialised" in result.output


def test_init_no_tui_flag(tmp_path):
    """--no-tui forces non-interactive init even in a TTY."""
    result = runner.invoke(app, ["init", "--path", str(tmp_path), "--no-tui"])
    assert result.exit_code == 0
    assert "Initialised" in result.output
    assert (tmp_path / ".kist" / "config.toml").exists()


# --- kist link ---


def test_link_success(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    runner.invoke(app, ["init", "--path", str(lib)])
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["link", str(lib)])
    assert result.exit_code == 0
    assert "Linked" in result.output
    assert (project / "kist.toml").exists()


def test_link_with_path(tmp_path):
    lib = tmp_path / "lib"
    runner.invoke(app, ["init", "--path", str(lib)])
    project = tmp_path / "project"
    project.mkdir()

    result = runner.invoke(app, ["link", str(lib), "--path", str(project)])
    assert result.exit_code == 0
    assert (project / "kist.toml").exists()


def test_link_invalid_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["link", str(tmp_path / "nope")])
    assert result.exit_code == 1
    assert "Not a kist library" in result.output


def test_link_already_linked(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    runner.invoke(app, ["init", "--path", str(lib)])
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    runner.invoke(app, ["link", str(lib)])
    result = runner.invoke(app, ["link", str(lib)])
    assert result.exit_code == 1
    assert "Already linked" in result.output
