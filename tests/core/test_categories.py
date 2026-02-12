"""Tests for the well-known category registry."""

from kist.core.categories import WELL_KNOWN_CATEGORIES
from kist.models.config import CategoryDef


def test_registry_has_all_16_categories():
    expected = {
        "RES",
        "CAP",
        "IND",
        "DIO",
        "TRAN",
        "IC",
        "CONN",
        "SW",
        "REL",
        "XTAL",
        "FUSE",
        "TFRM",
        "TP",
        "FID",
        "MECH",
        "MISC",
    }
    assert set(WELL_KNOWN_CATEGORIES.keys()) == expected


def test_all_entries_are_category_defs():
    for code, cat_def in WELL_KNOWN_CATEGORIES.items():
        assert isinstance(cat_def, CategoryDef), f"{code} is not a CategoryDef"


def test_all_entries_have_name_and_refdes():
    for code, cat_def in WELL_KNOWN_CATEGORIES.items():
        assert cat_def.name, f"{code} has no name"
        assert cat_def.refdes, f"{code} has no refdes"


def test_passives_have_symbol_template():
    assert WELL_KNOWN_CATEGORIES["RES"].symbol_template == "resistor"
    assert WELL_KNOWN_CATEGORIES["CAP"].symbol_template == "capacitor"
    assert WELL_KNOWN_CATEGORIES["IND"].symbol_template == "inductor"


def test_res_key_specs():
    res = WELL_KNOWN_CATEGORIES["RES"]
    assert res.key_specs == ["resistance", "tolerance"]
    assert res.value_field == "resistance"


def test_cap_subcategory_overrides():
    cap = WELL_KNOWN_CATEGORIES["CAP"]
    assert "CER" in cap.subcategory_key_specs
    assert "dielectric" in cap.subcategory_key_specs["CER"]
    assert cap.subcategory_names["CER"] == "Ceramic"


def test_ind_subcategory_overrides():
    ind = WELL_KNOWN_CATEGORIES["IND"]
    assert "FERRITE" in ind.subcategory_key_specs
    assert "impedance_100mhz" in ind.subcategory_key_specs["FERRITE"]


def test_dio_subcategory_overrides():
    dio = WELL_KNOWN_CATEGORIES["DIO"]
    assert "LED" in dio.subcategory_key_specs
    assert dio.subcategory_key_specs["LED"] == ["colour"]
    assert dio.subcategory_value_field["LED"] == "colour"
