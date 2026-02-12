"""Tests for the JSON parts database."""

import json
from pathlib import Path

import pytest

from kist.core.database import PartsDatabase, create_empty
from kist.errors import DuplicatePartError
from kist.models import (
    Ipn,
    JellybeanPart,
    ProprietaryPart,
    SemiJellybeanPart,
)

# -- create_empty -----------------------------------------------------------


def test_create_empty(tmp_path: Path):
    path = tmp_path / "parts.json"
    create_empty(path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data == {"version": 1, "parts": {}}


# -- load --------------------------------------------------------------------


def test_load_empty_database(db: PartsDatabase):
    assert db.list_parts() == []
    assert db.parts == {}


# -- add / get ---------------------------------------------------------------


def test_add_and_get(db: PartsDatabase, proprietary_part: ProprietaryPart):
    ipn = db.add(proprietary_part)

    assert isinstance(ipn, str)
    assert len(ipn) == 36  # UUID format

    retrieved = db.get(ipn)
    assert retrieved == proprietary_part


def test_add_and_resolve(db: PartsDatabase, proprietary_part: ProprietaryPart):
    ipn = db.add(proprietary_part)

    resolved = db.resolve(proprietary_part.name)
    assert resolved is not None
    assert resolved == ipn

    retrieved = db.get(resolved)
    assert retrieved == proprietary_part


def test_add_persists_to_disk(db: PartsDatabase, proprietary_part: ProprietaryPart):
    ipn = db.add(proprietary_part)

    # Load in a fresh instance
    db2 = PartsDatabase(db.path)
    db2.load()
    assert len(db2.list_parts()) == 1
    assert db2.get(ipn) == proprietary_part


def test_add_duplicate_name_raises(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    db.add(proprietary_part)

    with pytest.raises(DuplicatePartError):
        db.add(proprietary_part)


# -- remove ------------------------------------------------------------------


def test_remove(db: PartsDatabase, proprietary_part: ProprietaryPart):
    ipn = db.add(proprietary_part)
    removed = db.remove(ipn)

    assert removed == proprietary_part
    assert db.list_parts() == []
    assert db.get(ipn) is None
    assert db.resolve(proprietary_part.name) is None


def test_remove_missing_returns_none(db: PartsDatabase):
    assert db.remove(Ipn("00000000-0000-0000-0000-000000000000")) is None


# -- get / resolve missing ---------------------------------------------------


def test_get_missing_returns_none(db: PartsDatabase):
    assert db.get(Ipn("00000000-0000-0000-0000-000000000000")) is None


def test_resolve_missing_returns_none(db: PartsDatabase):
    assert db.resolve("DOES-NOT-EXIST") is None


# -- list_parts --------------------------------------------------------------


def test_list_parts_sorted(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    semi_jellybean_part: SemiJellybeanPart,
    jellybean_part: JellybeanPart,
):
    db.add(jellybean_part)  # RES-10K-1PCT-0603
    db.add(proprietary_part)  # IC-STM32F405RGT6-LQFP64
    db.add(semi_jellybean_part)  # IC-TL072-SO8

    names = [p.name for p in db.list_parts()]
    assert names == sorted(names)


# -- search ------------------------------------------------------------------


def test_search_by_name(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    jellybean_part: JellybeanPart,
):
    db.add(proprietary_part)
    db.add(jellybean_part)

    results = db.search("STM32")
    assert len(results) == 1
    assert results[0].name == "IC-STM32F405RGT6-LQFP64"


def test_search_by_description(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    jellybean_part: JellybeanPart,
):
    db.add(proprietary_part)
    db.add(jellybean_part)

    results = db.search("resistors")
    assert len(results) == 1
    assert results[0].name == "RES-10K-1PCT-0603"


def test_search_by_tag(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    jellybean_part: JellybeanPart,
):
    db.add(proprietary_part)
    db.add(jellybean_part)

    results = db.search("cortex")
    assert len(results) == 1
    assert results[0].name == "IC-STM32F405RGT6-LQFP64"


def test_search_by_mpn(db: PartsDatabase, semi_jellybean_part: SemiJellybeanPart):
    db.add(semi_jellybean_part)

    results = db.search("TL072CDR")
    assert len(results) == 1


def test_search_by_base_pn(db: PartsDatabase, semi_jellybean_part: SemiJellybeanPart):
    db.add(semi_jellybean_part)

    results = db.search("TL072")
    assert len(results) == 1


# -- Full roundtrip ----------------------------------------------------------


def test_roundtrip_all_tiers(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    semi_jellybean_part: SemiJellybeanPart,
    jellybean_part: JellybeanPart,
):
    """Add all three tiers, save, reload in fresh instance, verify."""
    parts = [proprietary_part, semi_jellybean_part, jellybean_part]
    ipns = [db.add(p) for p in parts]

    # Reload from disk
    db2 = PartsDatabase(db.path)
    db2.load()

    assert len(db2.list_parts()) == 3
    for ipn, original in zip(ipns, parts, strict=True):
        assert db2.get(ipn) == original
