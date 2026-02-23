# Concepts

## Library structure

kist manages a parts library stored in a `.kist/` directory:

```
my-library/
├── .kist/
│   ├── config.toml      # Library configuration and categories
│   ├── parts.json       # Part database (source of truth)
│   ├── symbols/         # Generated .kicad_sym files (one per category)
│   ├── footprints/
│   └── 3dmodels/
└── sym-lib-table        # KiCad library table (auto-managed)
```

When you link a KiCad project to a library with `kist link`, kist creates a `kist.toml` project reference and a `lib/` symlink. KiCad finds your symbols via `${KIPRJMOD}/lib/`.

## Three-tier part model

Parts are classified into three tiers based on how interchangeable they are:

| Tier | Example | Key fields |
|---|---|---|
| **Proprietary** | STM32F405 | MPN, manufacturer |
| **Semi-jellybean** | TL072 | MPN, manufacturer + alternates |
| **Jellybean** | 10K resistor | Specifications + alternates |

**Proprietary** parts are unique -- a specific chip required by your design. There are no substitutes.

**Semi-jellybean** parts have functional equivalents from multiple manufacturers. The TL072 op-amp is made by TI, ST, and others -- they're pin-compatible and interchangeable.

**Jellybean** parts are defined by their specifications, not by a specific MPN. Any 10K 1% 0603 resistor will do. kist tracks multiple alternates and lets you pick the best source.

## Canonical naming

Each part gets a name generated automatically from its category, specifications, and package:

- `RES-10K-1PCT-0603` -- 10K 1% resistor in 0603
- `CAP-100n-50V-X7R-0402` -- 100nF 50V X7R capacitor in 0402
- `IC-STM32F405RGT6-LQFP64` -- proprietary IC with MPN

Names, display values, and descriptions are all derived from structured data. `kist check` will flag parts whose stored name has drifted from what would be generated today.

## KiCad integration

When you save a part, kist:

1. Writes to `parts.json`
2. Generates or updates the appropriate `.kicad_sym` file (one per category)
3. Refreshes the `sym-lib-table` in your project directory

Resistor, capacitor, and inductor symbols are generated from built-in templates with correct graphics and pins. Other parts get a stub symbol with all KiCad properties set correctly.

## Categories

kist ships with 16 built-in categories (RES, CAP, IND, DIO, TRAN, IC, CONN, SW, REL, XTAL, FUSE, TFRM, TP, FID, MECH, MISC). Each category defines:

- A reference designator (R, C, L, ...)
- Key specification fields used for naming
- A value field for schematic display
- An optional symbol template

You can define your own categories and subcategories in the library config, or via the TUI's category manager.

## Configuration

kist uses two levels of configuration:

- **Global config** -- user-level defaults stored in `~/.config/kist/`. Theme, DigiKey API credentials, default suppliers.
- **Library config** -- per-library settings in `.kist/config.toml`. Directory names, supplier list, prefix/separator for naming, category definitions.

Library config is resolved at init time and is fully self-contained. All config files carry `version = 1` for forward compatibility.
