"""Tests for library health checks."""

import copy

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.core.check import check_library
from kist.core.database import PartsDatabase, create_empty
from kist.models.config import LibraryConfig


def _make_db(tmp_path, parts):
    """Create a loaded PartsDatabase with the given parts."""
    path = tmp_path / "parts.json"
    create_empty(path)
    db = PartsDatabase(path)
    db.load()
    for part in parts:
        db.add(part)
    return db


def test_clean_library_returns_empty(tmp_path, jellybean_part):
    db = _make_db(tmp_path, [jellybean_part])
    config = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))
    issues = check_library(db, config)
    assert issues == []


def test_empty_library_returns_empty(tmp_path):
    db = _make_db(tmp_path, [])
    config = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))
    issues = check_library(db, config)
    assert issues == []


def test_name_drift_detected(tmp_path, jellybean_part):
    jellybean_part.name = "WRONG-NAME"
    db = _make_db(tmp_path, [jellybean_part])
    config = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))

    issues = check_library(db, config)

    assert len(issues) == 1
    assert issues[0].kind == "name_drift"
    assert "WRONG-NAME" in issues[0].message
    assert issues[0].parts == ["WRONG-NAME"]


def test_duplicate_identity_detected(tmp_path, jellybean_part):
    part_a = jellybean_part
    part_b = copy.deepcopy(jellybean_part)
    part_b.name = "RES-10K-1PCT-0603-COPY"

    db = _make_db(tmp_path, [part_a, part_b])
    config = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))

    issues = check_library(db, config)

    dup_issues = [i for i in issues if i.kind == "duplicate_identity"]
    assert len(dup_issues) == 1
    assert len(dup_issues[0].parts) == 2


def test_both_issues_reported(tmp_path, jellybean_part):
    """A part with a wrong name that also collides with another."""
    part_a = jellybean_part
    part_b = copy.deepcopy(jellybean_part)
    part_b.name = "WRONG-NAME"

    db = _make_db(tmp_path, [part_a, part_b])
    config = LibraryConfig(categories=dict(WELL_KNOWN_CATEGORIES))

    issues = check_library(db, config)

    kinds = {i.kind for i in issues}
    assert "name_drift" in kinds
    assert "duplicate_identity" in kinds
