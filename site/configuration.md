# Configuration

## Library config

Each library stores its configuration in `.kist/config.toml`. All fields
are resolved at init time -- library config is fully self-contained.

```toml
version = 1
library_id = "a1b2c3d4-..."
library_prefix = "00k"
separator = "-"
symbols_dir = "symbols"
footprints_dir = "footprints"
models_dir = "3dmodels"
blocks_dir = "blocks"
suppliers = ["digikey", "mouser", "lcsc"]
digikey_locale = "US"
digikey_currency = "USD"
```

| Field | Type | Default | Description |
|---|---|---|---|
| `version` | int | `1` | Config format version. |
| `library_id` | string | *(generated)* | UUID assigned at init. Used by `kist link` to verify the target. |
| `library_prefix` | string | `"00k"` | Prefix for category library filenames (e.g. `00k-Resistors.kicad_sym`). |
| `separator` | string | `"-"` | Separator used in canonical part names. |
| `symbols_dir` | string | `"symbols"` | Directory name for generated `.kicad_sym` files. |
| `footprints_dir` | string | `"footprints"` | Directory name for footprint libraries. |
| `models_dir` | string | `"3dmodels"` | Directory name for 3D models. |
| `blocks_dir` | string | `"blocks"` | Directory name for design blocks. |
| `suppliers` | list | `["digikey", "mouser", "lcsc"]` | Supplier keys shown in the part form. |
| `digikey_locale` | string | `"US"` | DigiKey API locale. |
| `digikey_currency` | string | `"USD"` | DigiKey API currency. |
| `categories` | table | *(built-in set)* | Category definitions. See below. |

## Category definitions

Categories are defined under `[categories.CODE]` in the library config.
Each category controls how parts are named, what specs matter, and which
symbol template to use.

```toml
[categories.RES]
name = "Resistors"
refdes = "R"
key_specs = ["resistance", "tolerance"]
value_field = "resistance"
symbol_template = "resistor"
```

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | *(required)* | Human-readable category name. |
| `refdes` | string | *(required)* | KiCad reference designator (R, C, U, ...). |
| `key_specs` | list | `[]` | Specification fields used in canonical naming. |
| `subcategory_key_specs` | table | `{}` | Per-subcategory overrides for `key_specs`. |
| `subcategory_names` | table | `{}` | Human-readable names for subcategory codes. |
| `value_field` | string or list | `null` | Spec field(s) shown as the schematic value. |
| `subcategory_value_field` | table | `{}` | Per-subcategory overrides for `value_field`. |
| `value_field_separator` | string | `"/"` | Separator when `value_field` is a list. |
| `symbol_template` | string | `null` | Built-in symbol generator (`resistor`, `capacitor`, `inductor`). |

## Built-in categories

kist ships with 16 categories. Custom categories and subcategories can be
added in the library config or via the TUI's category manager.

| Code | Name | RefDes | Key specs | Subcategories |
|---|---|---|---|---|
| `RES` | Resistors | R | resistance, tolerance | -- |
| `CAP` | Capacitors | C | capacitance, voltage_rating | CER, ELEC, TANT, FILM |
| `IND` | Inductors | L | inductance, current_rating | FERRITE, CM, CHOKE |
| `DIO` | Diodes | D | reverse_voltage, forward_current | SCHOTTKY, ZENER, TVS, LED |
| `TRAN` | Transistors | Q | -- | NMOS, PMOS, NPN, PNP |
| `IC` | ICs | U | -- | -- |
| `CONN` | Connectors | J | -- | -- |
| `SW` | Switches | SW | -- | -- |
| `REL` | Relays | K | -- | -- |
| `XTAL` | Crystals | Y | frequency, load_capacitance | -- |
| `FUSE` | Fuses | F | current_rating, voltage_rating | PTC |
| `TFRM` | Transformers | T | -- | -- |
| `TP` | Test Points | TP | -- | -- |
| `FID` | Fiducials | FID | -- | -- |
| `MECH` | Mechanical | H | -- | -- |
| `MISC` | Miscellaneous | U | -- | -- |

## Global config

User-level defaults are stored in `~/.config/kist/config.toml`. These
values seed new libraries created with `kist init`.

```toml
theme = "null"
symbols_dir = "symbols"
footprints_dir = "footprints"
models_dir = "3dmodels"
blocks_dir = "blocks"
suppliers = ["digikey", "mouser", "lcsc"]

[providers.digikey]
enabled = true
client_id = "your-client-id"
client_secret = "your-client-secret"
```

| Field | Type | Default | Description |
|---|---|---|---|
| `theme` | string | `"null"` | TUI colour theme name. |
| `symbols_dir` | string | `"symbols"` | Default symbol directory for new libraries. |
| `footprints_dir` | string | `"footprints"` | Default footprint directory for new libraries. |
| `models_dir` | string | `"3dmodels"` | Default 3D model directory for new libraries. |
| `blocks_dir` | string | `"blocks"` | Default blocks directory for new libraries. |
| `suppliers` | list | `["digikey", "mouser", "lcsc"]` | Default supplier list for new libraries. |
| `providers.digikey.enabled` | bool | `true` | Enable DigiKey API integration. |
| `providers.digikey.client_id` | string | `null` | DigiKey API client ID. |
| `providers.digikey.client_secret` | string | `null` | DigiKey API client secret. |

The config directory can be overridden with the `KIST_CONFIG_DIR`
environment variable.

## Project reference

When you run `kist link`, a `kist.toml` file is created in your KiCad
project directory. This tells kist where to find the library.

```toml
version = 1
library_path = "../my-kicad-lib"
library_id = "a1b2c3d4-..."
```

| Field | Type | Description |
|---|---|---|
| `version` | int | Config format version. |
| `library_path` | string | Relative path from the project directory to the library root. |
| `library_id` | string | UUID of the linked library, for verification. |
