"""Tests for provider dispatch -- detect_provider and fetch_product."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kist.errors import ProviderError
from kist.providers import detect_provider, fetch_product
from kist.providers.models import ProviderProduct

# -- detect_provider ---------------------------------------------------------


def test_detect_digikey_url():
    url = "https://www.digikey.com/en/products/detail/yageo/RC0603FR-0710KL/726835"
    provider, identifier = detect_provider(url)
    assert provider == "digikey"
    assert identifier == "RC0603FR-0710KL"


def test_detect_digikey_au_url():
    url = (
        "https://www.digikey.com.au/en/products/detail/nordic/NPM1300-QEAA-R7/19722501"
    )
    provider, identifier = detect_provider(url)
    assert provider == "digikey"
    assert identifier == "NPM1300-QEAA-R7"


def test_detect_bare_mpn_defaults_to_digikey():
    provider, identifier = detect_provider("RC0603FR-0710KL")
    assert provider == "digikey"
    assert identifier == "RC0603FR-0710KL"


def test_detect_bare_mpn_strips_whitespace():
    provider, identifier = detect_provider("  RC0603FR-0710KL  ")
    assert provider == "digikey"
    assert identifier == "RC0603FR-0710KL"


def test_detect_unknown_url_raises():
    with pytest.raises(ProviderError, match="Unrecognised supplier URL"):
        detect_provider("https://www.example.com/some/product")


# -- fetch_product -----------------------------------------------------------


def _mock_provider_product() -> ProviderProduct:
    return ProviderProduct(
        mpn="RC0603FR-0710KL",
        manufacturer="Yageo",
        description="10k resistor",
        detailed_description="",
        supplier_name="DigiKey",
        supplier_sku="311-10.0KHRCT-ND",
        category="RES",
        parameters={"resistance": "10 kOhms"},
    )


@patch("kist.providers.DigiKeyClient")
@patch("kist.core.config.load_global_config")
@patch("kist.core.config.load_provider_mapping")
def test_fetch_product_digikey_url(
    mock_mapping, mock_config, mock_client_cls, monkeypatch
):
    """fetch_product dispatches to DigiKey for DigiKey URLs."""
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_ID", raising=False)
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_SECRET", raising=False)

    mock_mapping.return_value = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.providers.digikey.client_id = "test-id"
    mock_cfg.providers.digikey.client_secret = "test-secret"
    mock_config.return_value = mock_cfg

    expected = _mock_provider_product()
    mock_client_cls.return_value.fetch_product.return_value = expected

    result = fetch_product(
        "https://www.digikey.com/en/products/detail/yageo/RC0603FR-0710KL/726835"
    )

    assert result == expected
    mock_client_cls.assert_called_once_with("test-id", "test-secret")
    mock_client_cls.return_value.fetch_product.assert_called_once()


@patch("kist.providers.DigiKeyClient")
@patch("kist.core.config.load_global_config")
@patch("kist.core.config.load_provider_mapping")
def test_fetch_product_bare_mpn(
    mock_mapping, mock_config, mock_client_cls, monkeypatch
):
    """fetch_product dispatches bare MPNs to the default provider."""
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_ID", raising=False)
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_SECRET", raising=False)

    mock_mapping.return_value = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.providers.digikey.client_id = "test-id"
    mock_cfg.providers.digikey.client_secret = "test-secret"
    mock_config.return_value = mock_cfg

    expected = _mock_provider_product()
    mock_client_cls.return_value.fetch_product.return_value = expected

    result = fetch_product("RC0603FR-0710KL")

    assert result == expected


@patch("kist.core.config.load_global_config")
@patch("kist.core.config.load_provider_mapping")
def test_fetch_product_missing_credentials(mock_mapping, mock_config, monkeypatch):
    """fetch_product raises ProviderError when credentials are missing."""
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_ID", raising=False)
    monkeypatch.delenv("KIST_DIGIKEY_CLIENT_SECRET", raising=False)

    mock_mapping.return_value = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.providers.digikey.client_id = None
    mock_cfg.providers.digikey.client_secret = None
    mock_config.return_value = mock_cfg

    with pytest.raises(ProviderError, match="credentials not configured"):
        fetch_product("RC0603FR-0710KL")
