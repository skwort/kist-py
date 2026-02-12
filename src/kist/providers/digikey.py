"""DigiKey v4 API provider -- fetch product details by part number or URL."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from kist.errors import DigiKeyError
from kist.providers.models import DigiKeyProduct

# -- URLs -------------------------------------------------------------------

PRODUCTION_URL = "https://api.digikey.com"
SANDBOX_URL = "https://sandbox-api.digikey.com"

REQUEST_TIMEOUT = 30  # seconds

# -- Parameter mapping ------------------------------------------------------
# Maps DigiKey ParameterText names to kist spec field names.
# Parameters not in this map are preserved as-is in DigiKeyProduct.parameters.

PARAMETER_MAP: dict[str, str] = {
    "Resistance": "resistance",
    "Tolerance": "tolerance",
    "Capacitance": "capacitance",
    "Inductance": "inductance",
    "Voltage - Rated": "voltage_rating",
    "Voltage - Reverse Standoff (Typ)": "standoff_voltage",
    "Voltage - Zener (Nom) (Vz)": "zener_voltage",
    "Voltage - Collector Emitter Breakdown (Max)": "vceo",
    "Voltage - Drain to Source (Vdss)": "vds_max",
    "Current - Collector (Ic) (Max)": "ic_max",
    "Current - Drain (Id) (Max)": "id_max",
    "Current Rating (Amps)": "current_rating",
    "Current - Peak Pulse (10/1000\u00b5s)": "peak_current",
    "Forward Current (If)": "forward_current",
    "Power - Max": "power_rating",
    "Peak Pulse Power (Tp=8/20\u00b5s)": "peak_power",
    "Frequency": "frequency",
    "Frequency - Self Resonant": "srf",
    "Load Capacitance": "load_capacitance",
    "Impedance @ Frequency": "impedance",
    "Impedance": "impedance_100mhz",
    "Hold Current (Ih)": "hold_current",
    "Color": "colour",
}

# -- Category mapping -------------------------------------------------------
# Best-effort mapping from DigiKey category names to kist category codes.
# DigiKey has hundreds of subcategories; kist has ~16 top-level categories.
# Unknown categories return None -- the TUI will let the user pick.

CATEGORY_MAP: dict[str, str] = {
    "Resistors": "RES",
    "Chip Resistor - Surface Mount": "RES",
    "Through Hole Resistors": "RES",
    "Capacitors": "CAP",
    "Ceramic Capacitors": "CAP",
    "Aluminum Electrolytic Capacitors": "CAP",
    "Tantalum Capacitors": "CAP",
    "Film Capacitors": "CAP",
    "Inductors, Coils, Chokes": "IND",
    "Fixed Inductors": "IND",
    "Ferrite Beads and Chips": "IND",
    "Diodes - Rectifiers - Single": "DIO",
    "Diodes - Zener - Single": "DIO",
    "TVS - Diodes": "DIO",
    "LEDs": "DIO",
    "Transistors - MOSFETs": "TRAN",
    "Transistors - BJTs": "TRAN",
    "Transistors - FETs, MOSFETs - Single": "TRAN",
    "Transistors - Bipolar (BJT) - Single": "TRAN",
    "Integrated Circuits (ICs)": "IC",
    "Connectors": "CONN",
    "Connectors, Interconnects": "CONN",
    "Rectangular Connectors - Headers, Male Pins": "CONN",
    "Rectangular Connectors - Free Hanging, Panel Mount": "CONN",
    "USB, DVI, HDMI Connectors": "CONN",
    "Switches": "SW",
    "Relays": "REL",
    "Crystals": "XTAL",
    "Oscillators": "XTAL",
    "Fuses": "FUSE",
    "PTC Resettable Fuses": "FUSE",
    "Transformers": "TFRM",
}

# Parameter names that map to top-level DigiKeyProduct fields
_PACKAGE_PARAMS = {"Package / Case"}
_MOUNTING_PARAMS = {"Mounting Type"}


# -- URL parsing -------------------------------------------------------------


def parse_digikey_url(url: str) -> str:
    """
    Extract the manufacturer part number from a DigiKey URL.

    URL format: /en/products/detail/{mfr-slug}/{mpn}/{numeric-id}
    Returns the second-to-last path segment (the MPN), which is what
    the product details API accepts. If the input has no URL structure
    (no scheme/host), returns the string as-is -- it's assumed to be
    a bare part number already.
    """
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc:
        # Bare part number, not a URL
        return url.strip()
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        raise DigiKeyError(f"Cannot extract part number from URL: {url}")
    # MPN is the second-to-last segment; last is a numeric ID
    return segments[-2]


# -- Response mapping --------------------------------------------------------


def _find_category(category_node: dict | None) -> str | None:
    """Walk the category tree and return the first kist category match."""
    if not category_node:
        return None
    name = category_node.get("Name", "")
    if name in CATEGORY_MAP:
        return CATEGORY_MAP[name]
    # Check children -- DigiKey nests subcategories under the parent
    for child in category_node.get("ChildCategories", []):
        child_name = child.get("Name", "")
        if child_name in CATEGORY_MAP:
            return CATEGORY_MAP[child_name]
    return None


def _map_product(data: dict, digikey_pn: str) -> DigiKeyProduct:
    """Map a raw Product dict from the DigiKey API to DigiKeyProduct."""
    product = data.get("Product", data)

    description_obj = product.get("Description", {})
    manufacturer_obj = product.get("Manufacturer", {})

    # Build parameters dict, extracting package and mounting
    parameters: dict[str, str] = {}
    package: str | None = None
    mounting: str | None = None

    for param in product.get("Parameters", []):
        param_text = param.get("ParameterText", "")
        value_text = param.get("ValueText", "")
        if not param_text or not value_text:
            continue

        if param_text in _PACKAGE_PARAMS:
            package = value_text
        elif param_text in _MOUNTING_PARAMS:
            mounting = value_text

        # Map to kist spec name if known, otherwise keep original
        key = PARAMETER_MAP.get(param_text, param_text)
        parameters[key] = value_text

    # Get first variation's DigiKey part number if we don't have one
    dk_pn = digikey_pn
    variations = product.get("ProductVariations", [])
    if variations:
        dk_pn = variations[0].get("DigiKeyProductNumber", dk_pn)

    category = _find_category(product.get("Category"))

    return DigiKeyProduct(
        mpn=product.get("ManufacturerProductNumber", ""),
        manufacturer=manufacturer_obj.get("Name", ""),
        description=description_obj.get("ProductDescription", ""),
        detailed_description=description_obj.get("DetailedDescription", ""),
        digikey_pn=dk_pn,
        digikey_url=product.get("ProductUrl"),
        datasheet_url=product.get("DatasheetUrl"),
        category=category,
        parameters=parameters,
        unit_price=product.get("UnitPrice"),
        quantity_available=product.get("QuantityAvailable"),
        package=package,
        mounting=mounting,
    )


# -- Client ------------------------------------------------------------------


class DigiKeyClient:
    """
    DigiKey v4 API client.

    Credentials are injected at construction -- the client has no knowledge
    of config files or environment variables. Token is fetched lazily on
    first request and reused for subsequent calls.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        sandbox: bool = False,
        locale: str = "US",
        currency: str = "USD",
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = SANDBOX_URL if sandbox else PRODUCTION_URL
        self._locale = locale
        self._currency = currency
        self._token: str | None = None

    def _ensure_token(self) -> str:
        """Return a cached token, or fetch one via client_credentials grant."""
        if self._token is not None:
            return self._token

        resp = httpx.post(
            f"{self._base_url}/v1/oauth2/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            raise DigiKeyError(
                f"OAuth2 token request failed ({resp.status_code}): {resp.text}"
            )
        token_data = resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise DigiKeyError(f"No access_token in OAuth2 response: {token_data}")
        self._token = access_token
        return access_token

    def fetch_product(self, product_number: str) -> DigiKeyProduct:
        """
        Fetch product details from the DigiKey v4 API.

        Token is obtained lazily and reused across calls.
        """
        token = self._ensure_token()

        resp = httpx.get(
            f"{self._base_url}/products/v4/search/{product_number}/productdetails",
            headers={
                "Authorization": f"Bearer {token}",
                "X-DIGIKEY-Client-Id": self._client_id,
                "X-DIGIKEY-Locale-Site": self._locale,
                "X-DIGIKEY-Locale-Language": "en",
                "X-DIGIKEY-Locale-Currency": self._currency,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            raise DigiKeyError(
                f"Product details request failed ({resp.status_code}): {resp.text}"
            )

        return _map_product(resp.json(), product_number)
