# ADR-004: Configurable Categories

**Status**: Draft
**Date**: 2026-02-12

Supersedes ADR-001 SS3-4 (fixed Category enum), ADR-001 SS7 (hardcoded
key specs), and ADR-002 SS4 (hardcoded category-to-library mapping).

## Context

ADR-001 defines categories as a fixed `Category(StrEnum)` with 16
hardcoded values. The category-to-library mapping (ADR-002 SS4), the
category-to-refdes mapping, and the per-category key spec definitions
are all baked into source code. This is inflexible:

- Users cannot create categories that fit their domain (e.g. `OPTO`,
  `SENSOR`, `PSU`, `AUDIO`).
- Adding a category requires a code change, even though categories
  are purely data.
- The hardcoded mapping creates unnecessary coupling between the data
  model and the naming/KiCad layers.

Categories should be user-defined and stored in library configuration.
The tool suggests well-known defaults, but the user chooses which to
include and can add custom categories at any time.

### Requirements

- Users can add, remove, and modify categories without touching code.
- Each category defines its own refdes, key specs, and value display
  field.
- The naming engine and identity logic become data-driven, reading
  category definitions from config rather than hardcoded dicts.
- Existing spec normalisers (resistance, capacitance, etc.) remain in
  code -- they are functions, not data.
- Categories should evolve over time. Users should not be forced to
  define their full taxonomy upfront.
- `kist init` prompts the user to select from well-known categories.
  Only selected categories are written to config. More can be added
  later.
- The category config is the primary schema for `kist add`. The add
  workflow uses it to populate the category picker, determine which
  spec fields to prompt for, auto-generate name/value/description,
  and set default refdes. When the user needs a category that doesn't
  exist yet, the add flow should allow creating one inline rather
  than forcing the user to exit and configure separately.

## Decision

### 1. Categories in Library Config

Category definitions live in `.kist/config.toml` under a `[categories]`
table. Each category is a sub-table keyed by its short uppercase code.

```toml
version = 1
symbols_dir = "symbols"
footprints_dir = "footprints"
models_dir = "3dmodels"
blocks_dir = "blocks"
library_prefix = "00k"
separator = "-"
suppliers = ["digikey", "mouser", "lcsc"]

[categories.RES]
name = "Resistors"
refdes = "R"
value_field = "resistance"
key_specs = ["resistance", "tolerance"]
symbol_template = "resistor"

[categories.CAP]
name = "Capacitors"
refdes = "C"
value_field = "capacitance"
key_specs = ["capacitance", "voltage_rating"]
symbol_template = "capacitor"

[categories.CAP.subcategory_key_specs]
CER = ["capacitance", "voltage_rating", "dielectric"]
ELEC = ["capacitance", "voltage_rating"]
TANT = ["capacitance", "voltage_rating"]
FILM = ["capacitance", "voltage_rating"]

[categories.CAP.subcategory_names]
CER = "Ceramic"
ELEC = "Electrolytic"
TANT = "Tantalum"
FILM = "Film"

[categories.IC]
name = "ICs"
refdes = "U"
```

#### Category Fields

| Field                   | Type            | Required | Description                                           |
|-------------------------|-----------------|----------|-------------------------------------------------------|
| `name`                  | `str`           | yes      | Human-readable name ("Resistors")                     |
| `refdes`                | `str`           | yes      | Default reference designator ("R", "C", "U")          |
| `key_specs`             | `list[str]`     | no       | Default key spec fields for jellybean identity        |
| `subcategory_key_specs` | `table`         | no       | Per-subcategory overrides: `{SUBCAT = [fields...]}`   |
| `subcategory_names`     | `table`         | no       | Human-readable subcategory names: `{SUBCAT = "Name"}` |
| `value_field`           | `str\|list[str]` | no       | Spec field(s) for KiCad schematic display value       |
| `subcategory_value_field` | `table`       | no       | Per-subcategory overrides: `{SUBCAT = field(s)}`      |
| `value_field_separator` | `str`           | no       | Separator when `value_field` is a list (default `"/"`) |
| `symbol_template`       | `str`           | no       | Built-in symbol template (see §5 for valid names)     |

#### KiCad Library Naming

All kist-managed symbol libraries share a common prefix followed by
the category name: `{library_prefix}{separator}{name}`. Both
`library_prefix` and `separator` are configured at the library level
in `.kist/config.toml`, defaulting to `"00k"` and `"-"` respectively.
The separator is used throughout -- part names, library names, and
any other joined identifiers.

The default `00k` prefix groups kist libraries together in KiCad's
alphabetically-sorted symbol chooser. The `k` infix marks them as
kist-managed, distinguishing from user or standard libraries. Within
the prefix group, libraries sort alphabetically by name -- no
per-category numbering is needed.

This matches how KiCad footprint libraries work: named, not numbered.
The library name is derived from the prefix and category `name` field,
so no per-category library config is needed.

```
00k-Capacitors.kicad_sym
00k-Connectors.kicad_sym
00k-Diodes.kicad_sym
00k-ICs.kicad_sym
00k-Resistors.kicad_sym
...
```

A user who wants their kist libraries sorted differently can change
the prefix (e.g. `library_prefix = "99k"` to sort last, or
`library_prefix = "kist"` to group by name).

Categories without `key_specs` cannot have jellybean parts -- only
proprietary and semi-jellybean parts use such categories. This is
natural for categories like `IC` and `CONN` where parts are almost
never jellybean. This constraint is enforced at add time (the add
flow prevents selecting jellybean for such categories) and at check
time (`kist check` flags any that slip through via hand-edited JSON).

Categories without `value_field` use the part name as the schematic
display value (the existing fallback behaviour).

### 2. Removing the Category Enum

`Category(StrEnum)` is removed from `models/part.py`. The `category`
field on `PartBase` becomes a plain `str`. Validation shifts from
type-level to config-level -- a part's category must exist in the
library's category config, enforced by the CRUD layer and `kist check`.

`RefDes(StrEnum)` is also removed. The `reference` field on `PartBase`
becomes a plain `str`. IEEE 315 values are documented but not enforced
by the type system, allowing users to define custom reference
designators for custom categories.

The `CATEGORY_REFDES` dict is removed. Refdes defaults come from the
category config.

### 3. Data-Driven Naming Engine

The naming engine (`core/naming.py`) currently has three hardcoded
data structures that move to config:

**`KEY_SPECS`** -- Replaced by `key_specs` and `subcategory_key_specs`
in the category config. The lookup logic remains the same: try
subcategory override first, fall back to base `key_specs`.

All public naming functions (`generate_name`, `generate_value`,
`generate_description`, `get_identity`) gain a
`categories: dict[str, CategoryDef]` parameter. The function looks
up `part.category` internally, keeping lookup and error handling in
one place rather than at every call site.

The part name separator (currently hardcoded as `"-"`) becomes
configurable via the top-level `separator` field in
`.kist/config.toml`, defaulting to `"-"`. `generate_name` accepts
this as a separate parameter.

**`_CATEGORY_NAMES`** -- Replaced by the `name` field in category
config. **`_CAP_SUBCAT_NAMES`** -- Replaced by `subcategory_names` in
category config. Both are used for description generation.

`generate_description()` becomes a single generic path for all
categories: join key spec values, package, subcategory display name
(from `subcategory_names` if present), and category name (lowercase
of the config `name` field). Per-category description templates
(e.g. "thick film resistor") are removed.

**`CATEGORY_LIBRARY`** (in `kicad/mapping.py`) -- Removed. The library
name is derived from `library_prefix` and the category `name` field
as `{library_prefix}{separator}{name}`.

`SPEC_NORMALISERS` stays in code. Normalisers are functions keyed by
spec field name (e.g. `"resistance"` maps to `normalise_resistance`).
They are independent of which categories exist. A user who creates an
`OPTO` category with `key_specs = ["wavelength"]` benefits from
existing normalisers if the field name matches, and gets `str.upper`
as a fallback for unknown field names.

### 4. Value Generation

`generate_value()` currently dispatches on `Category.RES`,
`Category.CAP`, etc. with per-category formatting logic. This becomes
data-driven:

1. Look up `value_field` from the category config.
2. If `value_field` is a string, read that spec field's value and
   format it using the spec normaliser for that field name (the same
   `SPEC_NORMALISERS` used for name generation).
3. If `value_field` is a list, normalise each field and join them
   with `value_field_separator` (default `"/"`). This handles
   categories like diodes and ferrites where no single spec is
   sufficient: `["voltage_rating", "current_rating"]` produces
   `"60V/1A"`.
4. If `value_field` is not defined, fall back to the part name.

Name and value use the same normaliser output. A 10kΩ resistor
displays as `10K` on the schematic (matching the part name
`RES-10K-1PCT-0603`). This eliminates the need for separate
value-specific formatting tiers -- `_VALUE_RES_TIERS` is removed
along with the per-category dispatch in `generate_value()`.

### 5. KiCad Symbol Templates

The built-in symbol template functions for R, C, and L schematic
symbols remain in code -- they are KiCad graphics generators, not
data. The mapping from category to template moves to config via the
`symbol_template` field. The code maintains a lookup from template
name to generator function:

```python
_TEMPLATES = {
    "resistor": resistor_symbol,
    "resistor_iec": resistor_symbol_iec,
    "capacitor": capacitor_symbol,
    "inductor": inductor_symbol,
}
```

A category with `symbol_template = "resistor"` gets the US zigzag
resistor symbol; `"resistor_iec"` gets the IEC rectangle variant.
Categories without `symbol_template` (or with an unrecognised
value) use the stub symbol template. If a user wants a custom
schematic symbol, they provide it as an imported symbol, not a
generated template.

The well-known defaults for RES, CAP, and IND include the
appropriate `symbol_template` value, so users who select these
categories at init time get the right templates automatically.

### 6. Well-Known Categories and Init

The tool maintains a built-in registry of well-known categories with
sensible defaults for `refdes`, `key_specs`, `subcategory_key_specs`,
`value_field`, and `symbol_template`. This registry is used for
suggestions, not automatic seeding.

`kist init` prompts the user to select which categories to include
from the well-known set. Only the selected categories are written to
`.kist/config.toml`. The user can also skip selection entirely and
add categories later.

The well-known set includes the 16 categories from ADR-001:

| Code   | Name           | RefDes |
|--------|----------------|--------|
| `RES`  | Resistors      | `R`    |
| `CAP`  | Capacitors     | `C`    |
| `IND`  | Inductors      | `L`    |
| `DIO`  | Diodes         | `D`    |
| `TRAN` | Transistors    | `Q`    |
| `IC`   | ICs            | `U`    |
| `CONN` | Connectors     | `J`    |
| `SW`   | Switches       | `SW`   |
| `REL`  | Relays         | `K`    |
| `XTAL` | Crystals       | `Y`    |
| `FUSE` | Fuses          | `F`    |
| `TFRM` | Transformers   | `T`    |
| `TP`   | Test Points    | `TP`   |
| `FID`  | Fiducials      | `FID`  |
| `MECH` | Mechanical     | `H`    |
| `MISC` | Miscellaneous  | `U`    |

Representative defaults from the registry (categories not listed
here have only `name` and `refdes`):

| Code   | `key_specs`                        | `value_field`            | `symbol_template` |
|--------|------------------------------------|--------------------------|-------------------|
| `RES`  | `[resistance, tolerance]`          | `resistance`             | `resistor`        |
| `CAP`  | `[capacitance, voltage_rating]`    | `capacitance`            | `capacitor`       |
| `IND`  | `[inductance, current_rating]`     | `inductance`             | `inductor`        |
| `DIO`  | `[reverse_voltage, forward_current]` | `[reverse_voltage, forward_current]` |             |
| `XTAL` | `[frequency, load_capacitance]`    | `frequency`              |                   |

DIO uses `subcategory_key_specs` and `subcategory_value_field` to
handle divergent subcategories: LED overrides both to `[colour]` and
`colour`, ZENER to `[zener_voltage, power_rating]` and
`zener_voltage`, etc.

The registry also includes common extensions like `OPTO`, `SENSOR`,
`FILTER`, and `PSU` for interactive suggestions when adding new
categories.

### 7. Adding Categories

Categories can be added by editing `.kist/config.toml` directly, or
via a `kist category add` command that prompts for the required fields
and writes the config entry. If the category code matches a
well-known category, defaults are pre-filled.

The `kist add` TUI's category picker includes an option to create a
new category inline. Selecting it opens a nested flow: enter a code,
pick from well-known defaults or fill in fields manually, then return
to the add flow with the new category selected. This keeps the user
in context rather than forcing them to exit, configure, and restart.
The new category is written to `.kist/config.toml` immediately.

### 8. Validation

`kist check` validates:

- Every part's `category` field matches a category defined in config.
- Every part's `reference` field matches its category's default refdes
  (warning, not error -- per-part overrides are allowed).
- Jellybean parts have `key_specs` defined for their category (or
  category+subcategory).
- No two categories share the same `name` (which would produce
  duplicate library filenames).
- Category codes are uppercase alphanumeric.

### 9. Migration

`parts.json` stores `"category": "RES"` as a plain string --
loosening from enum to string requires no data migration.

The config format version stays at `1`. `kist init` now writes
`library_prefix` and the `[categories]` table as required parts of
`.kist/config.toml`. Existing dev libraries should be re-initialised.

## Consequences

### Positive

- **User-defined categories**: Users can model their domain without
  code changes. An audio engineer can add `CODEC`, `AMP`, `FILTER`.
  A power electronics engineer can add `IGBT`, `THYRISTOR`.
- **Simpler code**: The `Category(StrEnum)`, `CATEGORY_REFDES`,
  `CATEGORY_LIBRARY`, `KEY_SPECS`, and `_CATEGORY_NAMES` hardcoded
  dicts are all replaced by config reads. The naming engine becomes a
  generic data-driven pipeline.
- **Simpler library naming**: The per-category numbered prefixes
  (`00k-Resistors`, `01k-Capacitors`, ... `15k-Misc`) are replaced
  by a single user-configurable `library_prefix` shared across all
  categories. Libraries sort alphabetically within the prefix group.
  This avoids the problem of assigning numbers to user-defined
  categories, and lets users control sort position by choosing
  their prefix (default `00k`).
- **Self-contained config**: Per ADR-003, the library config remains
  fully self-contained. Categories are resolved at init time and
  stored. No runtime fallback needed.
- **Incremental growth**: Categories can be added as the library
  evolves. No need to predict the full taxonomy upfront.
- **No data migration**: Existing `parts.json` files work unchanged.

### Negative

- **Loss of type-level validation**: `category: Category` caught
  typos at parse time. `category: str` defers validation to the
  CRUD layer. A misspelled category in hand-edited JSON won't be
  caught until `kist check` or load time.
- **Config complexity**: `.kist/config.toml` grows with each
  category definition, including key specs and subcategory overrides.
  User-driven seeding at init keeps this proportional to what the
  user actually needs, but a library with many categories will have
  a longer config file.
- **Limited symbol templates**: Only a handful of built-in symbol
  templates exist (resistor, capacitor, inductor). User-defined
  categories without a matching template get the stub symbol. This
  is a pragmatic trade-off -- generating correct schematic symbols
  requires domain-specific graphics, not data.

### Neutral

- **Spec normalisers stay in code**: Functions like
  `normalise_resistance` cannot meaningfully be expressed as config
  data. They remain in `core/naming.py`, keyed by spec field name.
  A user-defined category benefits from existing normalisers when
  using standard field names.
- **Subcategories remain freeform**: This ADR does not change how
  subcategories work. They are still freeform strings, validated
  only by convention and `kist check`.
- **Well-known registry serves double duty**: The built-in category
  registry used by `kist init` for suggestions is also the primary
  test fixture source for naming engine tests. This keeps the
  registry's API importable and well-exercised.
