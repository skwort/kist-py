"""Tests for part data models."""

import pytest
from pydantic import TypeAdapter, ValidationError

from kist.models import (
    JellybeanPart,
    Mounting,
    Part,
    ProprietaryPart,
    SemiJellybeanPart,
    Tier,
)

part_adapter = TypeAdapter(Part)


# --- Roundtrip tests ---


@pytest.mark.parametrize(
    "part_fixture",
    ["proprietary_part", "semi_jellybean_part", "jellybean_part"],
)
def test_roundtrip(part_fixture: str, request: pytest.FixtureRequest):
    """Create each tier, dump to JSON-compatible dict, validate back."""
    original = request.getfixturevalue(part_fixture)
    data = original.model_dump(mode="json")
    restored = part_adapter.validate_python(data)
    assert restored == original


# --- Discrimination tests ---


def test_wrong_tier_literal_raises(proprietary_part: ProprietaryPart):
    """A proprietary part payload with tier='jellybean' and missing specs fails."""
    data = proprietary_part.model_dump(mode="json")
    data["tier"] = "jellybean"
    with pytest.raises(ValidationError):
        part_adapter.validate_python(data)


def test_missing_required_field_raises(proprietary_part: ProprietaryPart):
    """A proprietary part missing 'mpn' fails validation."""
    data = proprietary_part.model_dump(mode="json")
    del data["mpn"]
    with pytest.raises(ValidationError):
        part_adapter.validate_python(data)


def test_jellybean_requires_specifications(jellybean_part: JellybeanPart):
    """A jellybean part without specifications fails validation."""
    data = jellybean_part.model_dump(mode="json")
    del data["specifications"]
    with pytest.raises(ValidationError):
        part_adapter.validate_python(data)


def test_extra_fields_forbidden(proprietary_part: ProprietaryPart):
    """Extra fields are rejected by the model."""
    data = proprietary_part.model_dump(mode="json")
    data["bogus_field"] = "should fail"
    with pytest.raises(ValidationError):
        part_adapter.validate_python(data)


# --- Defaults tests ---


def test_optional_fields_default(proprietary_part: ProprietaryPart):
    """Optional fields default to None or empty collections."""
    assert proprietary_part.subcategory == "MCU"  # explicitly set
    assert proprietary_part.notes is None
    assert proprietary_part.datasheet is None
    assert proprietary_part.keywords == []
    assert proprietary_part.specifications is None
    assert proprietary_part.exclude_from_bom is False
    assert proprietary_part.exclude_from_board is False
    assert proprietary_part.footprint_variant is None
    assert proprietary_part.suppliers == {}


def test_semi_jellybean_alternates_default():
    """Semi-jellybean alternates default to empty list if not provided."""
    part = SemiJellybeanPart(
        name="IC-LM7805-TO220",
        tier=Tier.SEMI_JELLYBEAN,
        description="5V linear regulator",
        category="IC",
        base_pn="LM7805",
        mpn="LM7805CT",
        manufacturer="Onsemi",
        symbol="Regulator_Linear:LM7805",
        footprint="Package_TO_SOT_THT:TO-220-3_Vertical",
        value="LM7805",
        reference="U",
    )
    assert part.alternates == []


# --- Enum membership tests ---


def test_tier_members():
    assert set(Tier) == {"proprietary", "semi-jellybean", "jellybean"}


def test_mounting_members():
    assert set(Mounting) == {"smd", "tht", "other"}
