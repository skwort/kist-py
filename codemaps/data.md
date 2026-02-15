# Data Models

> Freshness: 2026-02-15

## Part Models (`src/kist/models/part.py`, 92 lines)

### Types

| Type | Line | Description |
|---|---|---|
| `Ipn` | :10 | `NewType("Ipn", str)` -- internal part number |
| `Part` | :88 | Discriminated union: `ProprietaryPart \| SemiJellybeanPart \| JellybeanPart` |

### Enums

| Enum | Line | Values |
|---|---|---|
| `Tier` | :13 | `proprietary`, `semi-jellybean`, `jellybean` |
| `Mounting` | :19 | `smd`, `tht`, `other` |
| `SupplierInfo` | :25 | BaseModel(sku, url=None) |
| `Alternate` | :30 | BaseModel(mpn, manufacturer, notes=None, suppliers={}) |

### Models

```
PartBase (abstract, extra="forbid")
├── name, description, category, subcategory?, package?, mounting?
├── datasheet?, tags[], notes?, symbol, footprint, value, reference
├── keywords[], specifications?, exclude_from_bom, exclude_from_board
├── footprint_variant?, suppliers{}
│
├── ProprietaryPart   (tier=proprietary)          :64
│   └── + mpn, manufacturer
│
├── SemiJellybeanPart (tier=semi-jellybean)        :70
│   └── + base_pn, mpn, manufacturer, alternates[]
│
└── JellybeanPart     (tier=jellybean)             :78
    └── + alternates[], specifications (required)
```

## Config Models (`src/kist/models/config.py`, 81 lines)

| Model | Line | Description |
|---|---|---|
| `DEFAULT_SUPPLIERS` | :7 | `["digikey", "mouser", "lcsc"]` |
| `CategoryDef` | :14 | Category definition (name, ref_des, subcategories, key_specs, value_field, template) |
| `LibraryConfig` | :32 | Per-library config (version, dirs, suppliers, prefix, separator, categories) |
| `DigiKeyProviderConfig` | :49 | Provider credentials (enabled, client_id, client_secret) |
| `ProvidersConfig` | :57 | All provider configs (digikey) |
| `GlobalConfig` | :63 | User-level defaults (theme, suppliers, prefix, separator, providers) |
| `ProjectRef` | :75 | Project --> library pointer (version, library_path, library_id) |

## Provider Models (`src/kist/providers/models.py`, 57 lines)

| Model | Line | Description |
|---|---|---|
| `ProviderMappingConfig` | :8 | Mapping config (parameter_map, category_map, mounting_map, subcategory_map) |
| `ProviderProduct` | :35 | Normalized product data (mpn, manufacturer, description, category, specs, etc.) |

## On-Disk Formats

### parts.json
```json
{
  "version": 1,
  "parts": {
    "<uuid>": { "tier": "...", "name": "...", ... }
  }
}
```

### .kist/config.toml
```toml
version = 1
symbols_dir = "symbols"
footprints_dir = "footprints"
models_dir = "3dmodels"
blocks_dir = "blocks"
suppliers = ["digikey", "mouser", "lcsc"]
prefix = ""
separator = "-"

[categories.RES]
name = "Resistors"
ref_des = "R"
key_specs = ["resistance", "tolerance", "power"]
value_field = "resistance"
template = "resistor"
subcategories = { chip = "Chip", network = "Network", ... }
```

### kist.toml (project ref)
```toml
version = 1
library_path = "../my-library"
library_id = ""
```

### .kicad_sym (KiCad symbol library)
S-expression format, managed by `kicad/symbols.py`. One file per category
(e.g. `00k-Resistors.kicad_sym`). Symbols named by part name.

### sym-lib-table (KiCad library table)
S-expression format, managed by `kicad/lib_table.py`. Kist entries tagged
with `(descr "kist-managed")` for safe merge with non-kist entries.
