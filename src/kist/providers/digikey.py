"""DigiKey v4 API provider -- fetch product details by part number or URL."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from kist.errors import DigiKeyError
from kist.providers.models import ProviderMappingConfig, ProviderProduct

# -- URLs -------------------------------------------------------------------

PRODUCTION_URL = "https://api.digikey.com"
SANDBOX_URL = "https://sandbox-api.digikey.com"

REQUEST_TIMEOUT = 30  # seconds

# -- Parameter mapping ------------------------------------------------------
# Maps raw DigiKey ParameterText names to normalised target names.
#
# The target name determines how the parameter is routed:
#   "package"      --> ProviderProduct.package  (top-level field)
#   "mounting"     --> ProviderProduct.mounting  (top-level field)
#   in ignore list --> dropped
#   anything else  --> ProviderProduct.parameters[target]
#
# Methodology: extracted by fetching 86 products across two real BOMs via
# the DigiKey v4 API, then analysing parameter frequency and usefulness.
# Re-run on a wider data set to discover new parameter names worth mapping.

PARAMETER_MAP: dict[str, str] = {
    # Extracted to top-level fields
    "Package / Case": "package",
    "Mounting Type": "mounting",
    # -- Passive specs ----------------------------------------------------------
    "Resistance": "resistance",
    "Tolerance": "tolerance",
    "Capacitance": "capacitance",
    "Inductance": "inductance",
    "Temperature Coefficient": "temp_coefficient",
    "Composition": "composition",
    "Power (Watts)": "power_rating",
    "ESR (Equivalent Series Resistance)": "esr",
    # -- Voltage ----------------------------------------------------------------
    "Voltage - Rated": "voltage_rating",
    "Voltage - Reverse Standoff (Typ)": "standoff_voltage",
    "Voltage - Zener (Nom) (Vz)": "zener_voltage",
    "Voltage - Collector Emitter Breakdown (Max)": "vceo",
    "Voltage - Drain to Source (Vdss)": "vds_max",
    "Voltage - Breakdown (Min)": "breakdown_voltage",
    "Voltage - Clamping (Max) @ Ipp": "clamping_voltage",
    "Voltage - Supply": "voltage_supply",
    "Voltage - Output (Min/Fixed)": "voltage_output",
    "Voltage - Output (Max)": "voltage_output_max",
    "Voltage - Input (Min)": "voltage_input_min",
    "Voltage - Input (Max)": "voltage_input_max",
    # -- Current ----------------------------------------------------------------
    "Current Rating (Amps)": "current_rating",
    "Current - Peak Pulse (10/1000\u00b5s)": "peak_current",
    "Forward Current (If)": "forward_current",
    "Current - Collector (Ic) (Max)": "ic_max",
    "Current - Drain (Id) (Max)": "id_max",
    "Current - Output": "current_output",
    "Current - Saturation (Isat)": "isat",
    "Hold Current (Ih)": "hold_current",
    # -- Power ------------------------------------------------------------------
    "Power - Max": "power_max",
    "Peak Pulse Power (Tp=8/20\u00b5s)": "peak_power",
    "Power - Peak Pulse": "peak_power_pulse",
    # -- Inductor specs ---------------------------------------------------------
    "DC Resistance (DCR)": "dcr",
    "Q @ Freq": "q_factor",
    # -- Frequency --------------------------------------------------------------
    "Frequency": "frequency",
    "Frequency - Self Resonant": "srf",
    "Frequency Tolerance": "frequency_tolerance",
    "Load Capacitance": "load_capacitance",
    "Impedance @ Frequency": "impedance",
    "Impedance": "impedance_100mhz",
    # -- IC / regulator ---------------------------------------------------------
    "Topology": "topology",
    "Protocol": "protocol",
    "Output Configuration": "output_config",
    # -- Misc -------------------------------------------------------------------
    "Color": "colour",
}

# -- Ignored parameters --------------------------------------------------------
# Parameters dropped entirely after name normalisation.  These are either
# boilerplate (present on nearly every product) or physical dimensions that
# don't help with part selection.

IGNORE_PARAMETERS: list[str] = [
    "Operating Temperature",
    "Features",
    "Supplier Device Package",
    "Size / Dimension",
    "Height - Seated (Max)",
    "Ratings",
    "Failure Rate",
    "Applications",
    "Thickness (Max)",
    "Lead Spacing",
    "Lead Style",
    "Number of Terminations",
    "DigiKey Programmable",
]

# -- Category mapping -------------------------------------------------------
# Best-effort mapping from DigiKey category names to kist category codes.
# DigiKey has hundreds of subcategories; kist has ~16 top-level categories.
# Unknown categories return None -- the TUI will let the user pick.

CATEGORY_MAP: dict[str, str] = {
    # -- Passives ---------------------------------------------------------------
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
    "Filters": "IND",
    "EMI/RFI Filters (LC, RC Networks)": "IND",
    # -- Diodes / TVS -----------------------------------------------------------
    "Diodes - Rectifiers - Single": "DIO",
    "Diodes - Zener - Single": "DIO",
    "TVS - Diodes": "DIO",
    "Transient Voltage Suppressors (TVS)": "DIO",
    "Circuit Protection": "DIO",
    "LEDs": "DIO",
    # -- Transistors -------------------------------------------------------------
    "Transistors - MOSFETs": "TRAN",
    "Transistors - BJTs": "TRAN",
    "Transistors - FETs, MOSFETs - Single": "TRAN",
    "Transistors - Bipolar (BJT) - Single": "TRAN",
    # -- ICs (including subcategories) ------------------------------------------
    "Integrated Circuits (ICs)": "IC",
    "Power Management (PMIC)": "IC",
    "Data Acquisition": "IC",
    "Embedded": "IC",
    "Interface": "IC",
    "Logic": "IC",
    "Memory": "IC",
    "RF and Wireless": "IC",
    "RF Transceiver ICs": "IC",
    "RF Transceiver Modules and Modems": "IC",
    "RF Front End (LNA + PA)": "IC",
    "Sensors, Transducers": "IC",
    "Humidity, Moisture Sensors": "IC",
    "Magnetic Sensors": "IC",
    "Motion Sensors": "IC",
    # -- Connectors --------------------------------------------------------------
    "Connectors": "CONN",
    "Connectors, Interconnects": "CONN",
    "Rectangular Connectors": "CONN",
    "Rectangular Connectors - Headers, Male Pins": "CONN",
    "Rectangular Connectors - Free Hanging, Panel Mount": "CONN",
    "USB, DVI, HDMI Connectors": "CONN",
    "Coaxial Connectors (RF)": "CONN",
    "FFC, FPC (Flat Flexible) Connectors": "CONN",
    "Memory Connectors": "CONN",
    "Terminal Blocks": "CONN",
    "Cable Assemblies": "CONN",
    "Flat Flex Ribbon Jumpers, Cables": "CONN",
    # -- Switches / Relays ------------------------------------------------------
    "Switches": "SW",
    "Slide Switches": "SW",
    "Relays": "REL",
    # -- Crystals / Oscillators -------------------------------------------------
    "Crystals": "XTAL",
    "Crystals, Oscillators, Resonators": "XTAL",
    "Oscillators": "XTAL",
    # -- Fuses / Transformers ---------------------------------------------------
    "Fuses": "FUSE",
    "PTC Resettable Fuses": "FUSE",
    "Transformers": "TFRM",
}

# -- Mounting value normalisation -------------------------------------------
# Maps raw DigiKey mounting strings to canonical values.

MOUNTING_MAP: dict[str, str] = {
    "Surface Mount": "smd",
    "Surface Mount, MLCC": "smd",
    "Surface Mount, Right Angle": "smd",
    "Through Hole": "tht",
    "Surface Mount, Right Angle; Through Hole": "tht",
}

# Target names that route to top-level ProviderProduct fields
# instead of the parameters dict.
_EXTRACT_FIELDS = frozenset({"package", "mounting"})


def default_mapping() -> ProviderMappingConfig:
    """Return built-in DigiKey mapping defaults."""
    return ProviderMappingConfig(
        supplier_name="DigiKey",
        categories=dict(CATEGORY_MAP),
        parameters=dict(PARAMETER_MAP),
        ignore_parameters=list(IGNORE_PARAMETERS),
        mounting=dict(MOUNTING_MAP),
    )


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


def _find_category(
    category_node: dict | None, categories: dict[str, str]
) -> str | None:
    """Walk the category tree and return the first kist category match."""
    if not category_node:
        return None
    name = category_node.get("Name", "")
    if name in categories:
        return categories[name]
    # Check children -- DigiKey nests subcategories under the parent
    for child in category_node.get("ChildCategories", []):
        child_name = child.get("Name", "")
        if child_name in categories:
            return categories[child_name]
    return None


def _map_product(
    data: dict,
    product_number: str,
    mapping: ProviderMappingConfig,
) -> ProviderProduct:
    """Map a raw Product dict from the DigiKey API to ProviderProduct."""
    product = data.get("Product", data)

    description_obj = product.get("Description", {})
    manufacturer_obj = product.get("Manufacturer", {})

    ignore = set(mapping.ignore_parameters)

    # Pipeline: normalise parameter names, then route.
    #   "package"      --> product.package
    #   "mounting"     --> product.mounting (value normalised via mapping.mounting)
    #   in ignore set  --> dropped
    #   anything else  --> product.parameters[target]
    parameters: dict[str, str] = {}
    package: str | None = None
    mounting: str | None = None

    for param in product.get("Parameters", []):
        raw_name = param.get("ParameterText", "")
        value = param.get("ValueText", "")
        if not raw_name or not value:
            continue

        # 1. Normalise name
        target = mapping.parameters.get(raw_name, raw_name)

        # 2. Route
        if target == "package":
            package = value
        elif target == "mounting":
            mounting = value
        elif target in ignore:
            continue
        else:
            parameters[target] = value

    # Normalise mounting value
    if mounting:
        mounting = mapping.mounting.get(mounting)

    # Get first variation's DigiKey part number if we don't have one
    dk_pn = product_number
    variations = product.get("ProductVariations", [])
    if variations:
        dk_pn = variations[0].get("DigiKeyProductNumber", dk_pn)

    category = _find_category(product.get("Category"), mapping.categories)

    # Normalise protocol-relative datasheet URLs
    datasheet_url = product.get("DatasheetUrl")
    if datasheet_url and datasheet_url.startswith("//"):
        datasheet_url = "https:" + datasheet_url

    return ProviderProduct(
        mpn=product.get("ManufacturerProductNumber", ""),
        manufacturer=manufacturer_obj.get("Name", ""),
        description=description_obj.get("ProductDescription", ""),
        detailed_description=description_obj.get("DetailedDescription", ""),
        supplier_name=mapping.supplier_name,
        supplier_sku=dk_pn,
        supplier_url=product.get("ProductUrl"),
        datasheet_url=datasheet_url,
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

    def fetch_product(
        self,
        product_number: str,
        mapping: ProviderMappingConfig | None = None,
    ) -> ProviderProduct:
        """
        Fetch product details from the DigiKey v4 API.

        Token is obtained lazily and reused across calls.
        """
        if mapping is None:
            mapping = default_mapping()

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

        return _map_product(resp.json(), product_number, mapping)
