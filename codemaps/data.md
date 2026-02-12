# Data Models

> Freshness: 2026-02-12

## Part Models (`src/kist/models/part.py`, 150 lines)

### Types

| Type | Line | Description |
|---|---|---|
| `Ipn` | :10 | `NewType("Ipn", str)` -- internal part number |
| `Part` | :147 | Discriminated union: `ProprietaryPart \| SemiJellybeanPart \| JellybeanPart` |

### Enums

| Enum | Line | Values |
|---|---|---|
| `Tier` | :13 | `proprietary`, `semi-jellybean`, `jellybean` |
| `Category` | :19 | `RES CAP IND DIO TRAN IC CONN SW REL XTAL FUSE TFRM TP FID MECH MISC` |
| `Mounting` | :38 | `smd`, `tht`, `other` |
| `RefDes` | :44 | `R C L D Q U J SW K Y F T TP FID H FL` |

### Constants

| Constant | Line | Description |
|---|---|---|
| `CATEGORY_REFDES` | :65 | Maps `Category` -> `RefDes` |

### Models

```
PartBase (abstract, extra="forbid")
├── name, description, category, subcategory?, package?, mounting?
├── datasheet?, tags[], notes?, symbol, footprint, value, reference
├── keywords[], specifications?, exclude_from_bom, exclude_from_board
├── footprint_variant?, suppliers{}
│
├── ProprietaryPart   (tier=proprietary)
│   └── + mpn, manufacturer
│
├── SemiJellybeanPart (tier=semi-jellybean)
│   └── + base_pn, mpn, manufacturer, alternates[]
│
└── JellybeanPart     (tier=jellybean)
    └── + alternates[], specifications (required)
```

| Model | Line |
|---|---|
| `SupplierInfo` | :85 |
| `Alternate` | :90 |
| `PartBase` | :97 |
| `ProprietaryPart` | :123 |
| `SemiJellybeanPart` | :129 |
| `JellybeanPart` | :137 |

## Config Models (`src/kist/models/config.py`, 39 lines)

| Model | Line | Description |
|---|---|---|
| `LibraryConfig` | :14 | Per-library config (version, dir names, suppliers) |
| `GlobalConfig` | :25 | User-level defaults (same fields, all optional) |
| `ProjectRef` | :35 | Project -> library pointer (version, library_path) |

| Constant | Line | Description |
|---|---|---|
| `DEFAULT_SUPPLIERS` | :7 | `["digikey", "mouser", "lcsc"]` |

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
```

### kist.toml (project ref)
```toml
version = 1
library_path = "../my-library"
```
