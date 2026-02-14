"""Tests for library operations: init, link, and discovery."""

import uuid

import pytest

from kist.core.config import load_library_config
from kist.core.library import find_library, init_library, link_library
from kist.errors import LibraryExistsError, LibraryNotFoundError


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setenv("KIST_CONFIG_DIR", str(tmp_path / "config"))


# --- init_library ---


def test_init_creates_structure(tmp_path):
    root = init_library(tmp_path / "lib")
    assert (root / ".kist" / "config.toml").exists()
    assert (root / "parts.json").exists()
    assert (root / "symbols").is_dir()
    assert (root / "footprints").is_dir()
    assert (root / "3dmodels").is_dir()
    assert (root / "blocks").is_dir()


def test_init_generates_library_id(tmp_path):
    root = init_library(tmp_path / "lib")
    config = load_library_config(root)
    assert config.library_id
    uuid.UUID(config.library_id)  # raises ValueError if not valid


def test_init_respects_overrides(tmp_path):
    root = init_library(tmp_path / "lib", symbols_dir="sym", footprints_dir="fp")
    assert (root / "sym").is_dir()
    assert (root / "fp").is_dir()
    assert not (root / "symbols").exists()
    assert not (root / "footprints").exists()


def test_init_rejects_already_initialised(tmp_path):
    init_library(tmp_path / "lib")
    with pytest.raises(LibraryExistsError, match="Already initialised"):
        init_library(tmp_path / "lib")


def test_init_preserves_existing_dirs(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "symbols").mkdir()
    (lib / "symbols" / "existing.kicad_sym").touch()
    init_library(lib)
    assert (lib / "symbols" / "existing.kicad_sym").exists()


def test_init_preserves_existing_parts_json(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "parts.json").write_text('{"version": 1, "parts": {"a": "b"}}')
    init_library(lib)
    assert '"a"' in (lib / "parts.json").read_text()


# --- link_library ---


def test_link_creates_ref_and_symlink(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    project = tmp_path / "project"
    project.mkdir()

    ref_path = link_library(project, lib)
    assert ref_path.exists()
    content = ref_path.read_text()
    assert "library_path" in content
    assert "library_id" in content
    assert (project / "lib").is_symlink()


def test_link_stores_library_id(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    lib_config = load_library_config(lib)
    project = tmp_path / "project"
    project.mkdir()

    link_library(project, lib)

    from kist.core.config import load_project_ref

    ref = load_project_ref(project / "kist.toml")
    assert ref.library_id == lib_config.library_id


def test_link_skips_existing_lib_dir(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    project = tmp_path / "project"
    project.mkdir()
    (project / "lib").mkdir()  # e.g. git submodule

    link_library(project, lib)
    assert not (project / "lib").is_symlink()
    assert (project / "lib").is_dir()


def test_link_rejects_invalid_library(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    not_a_lib = tmp_path / "not-a-lib"
    not_a_lib.mkdir()

    with pytest.raises(LibraryNotFoundError, match="Not a kist library"):
        link_library(project, not_a_lib)


def test_link_rejects_already_linked(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    project = tmp_path / "project"
    project.mkdir()

    link_library(project, lib)
    with pytest.raises(LibraryExistsError, match="Already linked"):
        link_library(project, lib)


# --- find_library ---


def test_find_from_library_root(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    result = find_library(lib)
    assert result.library_root == lib.resolve()
    assert result.project_dir is None


def test_find_from_subdirectory(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    subdir = lib / "symbols" / "deep"
    subdir.mkdir(parents=True)
    assert find_library(subdir).library_root == lib.resolve()


def test_find_via_project_ref(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    project = tmp_path / "project"
    project.mkdir()
    link_library(project, lib)
    result = find_library(project)
    assert result.library_root == lib.resolve()
    assert result.project_dir == project.resolve()


def test_find_via_nested_subdir_to_project_ref(tmp_path):
    lib = tmp_path / "lib"
    init_library(lib)
    project = tmp_path / "project"
    project.mkdir()
    link_library(project, lib)
    subdir = project / "boards" / "rev-a"
    subdir.mkdir(parents=True)
    result = find_library(subdir)
    assert result.library_root == lib.resolve()
    assert result.project_dir == project.resolve()


def test_find_not_found(tmp_path):
    with pytest.raises(LibraryNotFoundError, match="Not a kist library"):
        find_library(tmp_path)


def test_find_invalid_reference(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "kist.toml").write_text('version = 1\nlibrary_path = "../nonexistent"\n')
    with pytest.raises(LibraryNotFoundError, match="not a kist library"):
        find_library(project)


def test_find_prefers_kist_marker_over_ref(tmp_path):
    """When both .kist/ and kist.toml exist, .kist/ wins."""
    lib = tmp_path / "lib"
    init_library(lib)
    # Also drop a kist.toml pointing elsewhere
    (lib / "kist.toml").write_text('version = 1\nlibrary_path = "../other"\n')
    assert find_library(lib).library_root == lib.resolve()


def test_find_uses_cwd_default(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    init_library(lib)
    monkeypatch.chdir(lib)
    assert find_library().library_root == lib.resolve()


# --- project_dir discovery from library root ---


def test_find_discovers_project_from_library(tmp_path):
    """When inside the library, check parent for kist.toml."""
    project = tmp_path / "project"
    project.mkdir()
    lib = project / "lib"
    init_library(lib)
    link_library(project, lib)

    result = find_library(lib)
    assert result.library_root == lib.resolve()
    assert result.project_dir == project.resolve()


def test_find_no_project_when_parent_has_no_ref(tmp_path):
    """Library root with no kist.toml in parent returns no project_dir."""
    lib = tmp_path / "lib"
    init_library(lib)
    result = find_library(lib)
    assert result.project_dir is None


def test_find_no_project_when_parent_ref_points_elsewhere(tmp_path):
    """kist.toml in parent that points to a different library is ignored."""
    project = tmp_path / "project"
    project.mkdir()
    lib = project / "lib"
    init_library(lib)
    # kist.toml points to a different library
    other_lib = tmp_path / "other-lib"
    init_library(other_lib)
    link_library(project, other_lib)

    result = find_library(lib)
    assert result.library_root == lib.resolve()
    assert result.project_dir is None
