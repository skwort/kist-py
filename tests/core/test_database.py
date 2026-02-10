"""Tests for the JSON parts database."""

import json
from pathlib import Path

import pytest

from kist.core.database import PartsDatabase, create_empty
from kist.errors import DuplicatePartError, PartNotFoundError
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


def test_add_and_get_by_name(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    uid = db.add(proprietary_part)

    assert isinstance(uid, str)
    assert len(uid) == 36  # UUID format

    retrieved = db.get(proprietary_part.name)
    assert retrieved == proprietary_part


def test_add_and_get_by_id(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    uid = db.add(proprietary_part)

    retrieved = db.get_by_id(uid)
    assert retrieved == proprietary_part


def test_add_persists_to_disk(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    db.add(proprietary_part)

    # Load in a fresh instance
    db2 = PartsDatabase(db.path)
    db2.load()
    assert len(db2.list_parts()) == 1
    assert db2.get("IC-STM32F405RGT6-LQFP64").mpn == "STM32F405RGT6"  # type: ignore[union-attr]


def test_add_duplicate_name_raises(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    db.add(proprietary_part)

    with pytest.raises(DuplicatePartError):
        db.add(proprietary_part)


# -- remove ------------------------------------------------------------------


def test_remove_by_name(
    db: PartsDatabase, proprietary_part: ProprietaryPart
):
    db.add(proprietary_part)
    db.remove(proprietary_part.name)

    assert db.list_parts() == []
    with pytest.raises(PartNotFoundError):
        db.get(proprietary_part.name)


def test_remove_missing_raises(db: PartsDatabase):
    with pytest.raises(PartNotFoundError):
        db.remove("DOES-NOT-EXIST")


# -- get missing -------------------------------------------------------------


def test_get_missing_name_raises(db: PartsDatabase):
    with pytest.raises(PartNotFoundError):
        db.get("DOES-NOT-EXIST")


def test_get_by_id_missing_raises(db: PartsDatabase):
    with pytest.raises(PartNotFoundError):
        db.get_by_id(Ipn("00000000-0000-0000-0000-000000000000"))


# -- list_parts --------------------------------------------------------------


def test_list_parts_sorted(
    db: PartsDatabase,
    proprietary_part: ProprietaryPart,
    semi_jellybean_part: SemiJellybeanPart,
    jellybean_part: JellybeanPart,
):
    db.add(jellybean_part)       # RES-10K-1PCT-0603
    db.add(proprietary_part)     # IC-STM32F405RGT6-LQFP64
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

    results = db.search("thick film")
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


def test_search_by_mpn(
    db: PartsDatabase, semi_jellybean_part: SemiJellybeanPart
):
    db.add(semi_jellybean_part)

    results = db.search("TL072CDR")
    assert len(results) == 1


def test_search_by_base_pn(
    db: PartsDatabase, semi_jellybean_part: SemiJellybeanPart
):
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
    uids = [db.add(p) for p in parts]

    # Reload from disk
    db2 = PartsDatabase(db.path)
    db2.load()

    assert len(db2.list_parts()) == 3
    for uid, original in zip(uids, parts, strict=True):
        assert db2.get_by_id(uid) == original
