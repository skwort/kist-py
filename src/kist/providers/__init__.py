"""Provider dispatch -- detect provider from input and fetch product data."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from kist.errors import ProviderError
from kist.providers.digikey import DigiKeyClient, parse_digikey_url
from kist.providers.models import ProviderProduct

if TYPE_CHECKING:
    from kist.models.config import GlobalConfig
    from kist.providers.models import ProviderMappingConfig

# Host patterns that identify a provider from a URL.
_HOST_PROVIDERS: dict[str, str] = {
    "digikey": "digikey",
}


def detect_provider(url_or_mpn: str) -> tuple[str, str]:
    """
    Return (provider_name, identifier) from a URL or bare MPN.

    For URLs, the host is matched against known providers. The
    identifier is extracted by the provider's URL parser.

    For bare input (no scheme/host), defaults to "digikey".

    Raises ProviderError for URLs with unrecognised hosts.
    """
    parsed = urlparse(url_or_mpn.strip())

    if not parsed.scheme and not parsed.netloc:
        # Bare MPN -- default provider
        return "digikey", url_or_mpn.strip()

    # Match host against known providers
    host = (parsed.netloc or "").lower()
    for pattern, provider in _HOST_PROVIDERS.items():
        if pattern in host:
            if provider == "digikey":
                return provider, parse_digikey_url(url_or_mpn)
            return provider, url_or_mpn.strip()

    raise ProviderError(f"Unrecognised supplier URL: {url_or_mpn}")


def fetch_product(url_or_mpn: str) -> ProviderProduct:
    """
    Detect provider, load credentials and mapping, fetch product.

    This is the single entry point the TUI uses. It handles:
    1. Provider detection from the input
    2. Credential loading from global config / env vars
    3. Mapping config loading (built-in defaults + user TOML)
    4. API call via the provider client
    """
    from kist.core.config import load_global_config, load_provider_mapping

    provider_name, identifier = detect_provider(url_or_mpn)
    global_cfg = load_global_config()
    mapping = load_provider_mapping(provider_name)

    if provider_name == "digikey":
        return _fetch_digikey(identifier, mapping, global_cfg)

    raise ProviderError(f"Provider not implemented: {provider_name}")


def _fetch_digikey(
    product_number: str,
    mapping: ProviderMappingConfig,
    global_cfg: GlobalConfig,
) -> ProviderProduct:
    """Build DigiKey client from credentials and fetch product details."""
    dk_cfg = global_cfg.providers.digikey

    client_id = os.environ.get("KIST_DIGIKEY_CLIENT_ID") or dk_cfg.client_id
    client_secret = os.environ.get("KIST_DIGIKEY_CLIENT_SECRET") or dk_cfg.client_secret

    if not client_id or not client_secret:
        raise ProviderError("DigiKey credentials not configured")

    client = DigiKeyClient(client_id, client_secret)
    return client.fetch_product(product_number, mapping)
