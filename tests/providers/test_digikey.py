"""Tests for the DigiKey provider."""

import pytest

from kist.errors import DigiKeyError
from kist.providers.digikey import (
    CATEGORY_MAP,
    PARAMETER_MAP,
    _map_product,
    default_mapping,
    parse_digikey_url,
)
from kist.providers.models import ProviderMappingConfig

# -- parse_digikey_url -------------------------------------------------------


def test_parse_full_url():
    url = "https://www.digikey.com.au/en/products/detail/nordic-semiconductor-asa/NPM1300-QEAA-R7/19722501"
    assert parse_digikey_url(url) == "NPM1300-QEAA-R7"


def test_parse_full_url_trailing_slash():
    url = "https://www.digikey.com/en/products/detail/yageo/RC0603FR-0710KL/726835/"
    assert parse_digikey_url(url) == "RC0603FR-0710KL"


def test_parse_url_with_query_params():
    url = "https://www.digikey.com/en/products/detail/murata/GRM188R71C104KA01D/587569?s=N4IgTCBcDaIIwFYBsAOAtHALgUwM4BcoA"
    assert parse_digikey_url(url) == "GRM188R71C104KA01D"


def test_parse_bare_part_number():
    assert parse_digikey_url("311-10.0KHRCT-ND") == "311-10.0KHRCT-ND"


def test_parse_bare_part_number_whitespace():
    assert parse_digikey_url("  311-10.0KHRCT-ND  ") == "311-10.0KHRCT-ND"


def test_parse_numeric_id():
    assert parse_digikey_url("19722501") == "19722501"


def test_parse_empty_path_raises():
    with pytest.raises(DigiKeyError, match="Cannot extract"):
        parse_digikey_url("https://www.digikey.com")


# -- _map_product ------------------------------------------------------------

_DEFAULT = default_mapping()

# Minimal API response structure matching DigiKey v4 ProductDetails
SAMPLE_RESPONSE = {
    "Product": {
        "ManufacturerProductNumber": "RC0603FR-0710KL",
        "Manufacturer": {"Name": "Yageo"},
        "Description": {
            "ProductDescription": "RES 10K OHM 1% 1/10W 0603",
            "DetailedDescription": "10 kOhms +/-1% 0.1W, 1/10W Chip Resistor 0603 (1608 Metric) Moisture Resistant Thick Film",
        },
        "ProductUrl": "https://www.digikey.com/en/products/detail/yageo/RC0603FR-0710KL/726835",
        "DatasheetUrl": "https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_12.pdf",
        "UnitPrice": 0.10,
        "QuantityAvailable": 28890000,
        "Category": {
            "Name": "Resistors",
            "ChildCategories": [
                {"Name": "Chip Resistor - Surface Mount", "ChildCategories": []}
            ],
        },
        "Parameters": [
            {
                "ParameterId": 2085,
                "ParameterText": "Resistance",
                "ValueText": "10 kOhms",
            },
            {
                "ParameterId": 3,
                "ParameterText": "Tolerance",
                "ValueText": "\u00b11%",
            },
            {
                "ParameterId": 2499,
                "ParameterText": "Power (Watts)",
                "ValueText": "0.1W, 1/10W",
            },
            {
                "ParameterId": 16,
                "ParameterText": "Package / Case",
                "ValueText": "0603 (1608 Metric)",
            },
            {
                "ParameterId": 69,
                "ParameterText": "Mounting Type",
                "ValueText": "Surface Mount",
            },
        ],
        "ProductVariations": [
            {
                "DigiKeyProductNumber": "311-10.0KHRCT-ND",
                "PackageType": {"Name": "Cut Tape"},
                "StandardPricing": [
                    {"BreakQuantity": 1, "UnitPrice": 0.10, "TotalPrice": 0.10}
                ],
            }
        ],
    }
}


def test_map_basic_fields():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.mpn == "RC0603FR-0710KL"
    assert result.manufacturer == "Yageo"
    assert result.description == "RES 10K OHM 1% 1/10W 0603"
    assert "10 kOhms" in result.detailed_description


def test_map_supplier_sku_from_variation():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.supplier_sku == "311-10.0KHRCT-ND"


def test_map_supplier_name():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.supplier_name == "DigiKey"


def test_map_urls():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.supplier_url is not None
    assert "digikey.com" in result.supplier_url
    assert result.datasheet_url is not None
    assert "yageo.com" in result.datasheet_url


def test_map_pricing_and_stock():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.unit_price == 0.10
    assert result.quantity_available == 28890000


def test_map_category():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.category == "RES"


def test_map_package_extracted():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.package == "0603 (1608 Metric)"


def test_map_mounting_normalised():
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.mounting == "smd"


def test_map_parameters_renamed():
    """Known parameters should be renamed to kist spec names."""
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.parameters["resistance"] == "10 kOhms"
    assert result.parameters["tolerance"] == "\u00b11%"


def test_map_unknown_parameters_preserved():
    """Parameters not in PARAMETER_MAP keep their original name."""
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert result.parameters["Power (Watts)"] == "0.1W, 1/10W"


def test_map_no_variations_keeps_input_pn():
    """When no ProductVariations exist, use the input part number."""
    data = {
        "Product": {
            **SAMPLE_RESPONSE["Product"],
            "ProductVariations": [],
        }
    }
    result = _map_product(data, "726835", _DEFAULT)
    assert result.supplier_sku == "726835"


def test_map_unknown_category_returns_none():
    data = {
        "Product": {
            **SAMPLE_RESPONSE["Product"],
            "Category": {
                "Name": "Some Unknown DigiKey Category",
                "ChildCategories": [],
            },
        }
    }
    result = _map_product(data, "726835", _DEFAULT)
    assert result.category is None


def test_map_missing_optional_fields():
    """Minimal response with only required fields."""
    data = {
        "Product": {
            "ManufacturerProductNumber": "TEST-123",
            "Manufacturer": {"Name": "TestCorp"},
            "Description": {
                "ProductDescription": "Test part",
                "DetailedDescription": "A test part",
            },
        }
    }
    result = _map_product(data, "TEST-123", _DEFAULT)
    assert result.mpn == "TEST-123"
    assert result.unit_price is None
    assert result.quantity_available is None
    assert result.package is None
    assert result.mounting is None
    assert result.parameters == {}
    assert result.category is None


def test_map_extracted_params_excluded():
    """Package and mounting are routed to top-level fields, not parameters."""
    result = _map_product(SAMPLE_RESPONSE, "726835", _DEFAULT)
    assert "package" not in result.parameters
    assert "mounting" not in result.parameters
    # Raw names should also be absent (they were normalised first)
    assert "Package / Case" not in result.parameters
    assert "Mounting Type" not in result.parameters


def test_map_ignored_params_excluded():
    """Parameters in ignore_parameters are dropped entirely."""
    custom = ProviderMappingConfig(
        supplier_name="DigiKey",
        categories=dict(CATEGORY_MAP),
        parameters=dict(PARAMETER_MAP),
        ignore_parameters=["resistance"],
        mounting={"Surface Mount": "smd"},
    )
    result = _map_product(SAMPLE_RESPONSE, "726835", custom)
    assert "resistance" not in result.parameters


def test_map_custom_category_mapping():
    """Custom mapping overrides change how categories are resolved."""
    custom = ProviderMappingConfig(
        supplier_name="DigiKey",
        categories={"Resistors": "CUSTOM"},
        parameters=dict(PARAMETER_MAP),
        mounting={"Surface Mount": "smd"},
    )
    result = _map_product(SAMPLE_RESPONSE, "726835", custom)
    assert result.category == "CUSTOM"


def test_map_unknown_mounting_returns_none():
    """Mounting values not in the mapping produce None."""
    custom = ProviderMappingConfig(
        supplier_name="DigiKey",
        categories=dict(CATEGORY_MAP),
        parameters=dict(PARAMETER_MAP),
        mounting={},  # empty -- no normalisation
    )
    result = _map_product(SAMPLE_RESPONSE, "726835", custom)
    assert result.mounting is None


def test_map_protocol_relative_datasheet():
    """Protocol-relative datasheet URLs get https: prefix."""
    data = {
        "Product": {
            **SAMPLE_RESPONSE["Product"],
            "DatasheetUrl": "//www.yageo.com/datasheet.pdf",
        }
    }
    result = _map_product(data, "726835", _DEFAULT)
    assert result.datasheet_url == "https://www.yageo.com/datasheet.pdf"


# -- Mapping dicts -----------------------------------------------------------


def test_parameter_map_values_are_snake_case():
    for dk_name, kist_name in PARAMETER_MAP.items():
        assert kist_name == kist_name.lower(), (
            f"PARAMETER_MAP[{dk_name!r}] = {kist_name!r} is not lowercase"
        )
        assert " " not in kist_name, (
            f"PARAMETER_MAP[{dk_name!r}] = {kist_name!r} contains spaces"
        )


def test_category_map_values_are_uppercase():
    for dk_name, kist_code in CATEGORY_MAP.items():
        assert kist_code == kist_code.upper(), (
            f"CATEGORY_MAP[{dk_name!r}] = {kist_code!r} is not uppercase"
        )
