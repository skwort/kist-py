# ADR-001: Part Data Model

**Status**: Draft
**Date**: 2026-02-10

## Context

KIP manages a KiCad component library as a JSON file tracked in Git. The
data model must support:

1. Three tiers of component abstraction (proprietary, semi-jellybean,
   jellybean) reflecting how engineers actually think about parts
2. Stable part identity that survives renames and spec changes
3. Flexible specifications that vary by component category without
   requiring schema changes per category
4. Supplier and sourcing data
5. KiCad integration fields (symbol, footprint, value)
6. A human-readable structured name generated deterministically from
   part fields, used as the label in the CLI and KiCad's symbol chooser

### Research Findings

Analysis of existing tools (InvenTree, PartsBox, GitPLM, Ki-nTree) and
community practices revealed:

- Every serious tool uses a stable internal identifier, not a
  human-readable name, as the primary key. InvenTree auto-generates
  IPNs, PartsBox uses opaque stable IDs, GitPLM encodes category in
  the IPN prefix.
- InvenTree separates parameter *templates* from parameter *values*;
  PartsBox uses "meta-parts" for jellybean alternates; GitPLM uses
  CSV-to-SQLite pipelines.
- The `.kicad_dbl` (database library) approach is powerful but the ODBC
  driver setup is the #1 community complaint. The `.kicad_httplib` API
  (KiCad 8+) is a cleaner integration path for future work.
- The KiCad Library Convention (KLC) uses generic symbols for passives
  (`R`, `C`, `L`) and MPN-based names for specific parts.
- Alternates are a first-class concept in every mature tool — for
  jellybean parts, the "part" is the specification and MPNs are
  sourcing options underneath.
- KiCad's symbol chooser sorts alphabetically. Users commonly prefix
  library names with numbers (`00-Resistors`, `01-Capacitors`) to
  control ordering.

### The Three Tiers

The three-tier classification emerged from how practising engineers
categorise components:

**Tier 1 — Proprietary**: A specific manufacturer's part with no
substitute. The design depends on this exact part. Examples:
STM32F405RGT6, WM8960CGEFL, a specific Molex connector series.

**Tier 2 — Semi-jellybean**: Function is standardised across
manufacturers. Pin-compatible, functionally equivalent parts exist. You
have a preferred MPN but alternates are acceptable. Examples: TL072
(TI/ST/Onsemi), LM7805, 74HC logic family.

**Tier 3 — Jellybean**: Selected entirely by specifications. Any
manufacturer's 10K 1% 0402 resistor will do. The schematic doesn't care
about the MPN. Examples: chip resistors, MLCCs, standard LEDs.

## Decision

### 1. UUID as Primary Key, Structured Name as Label

Each part gets a UUID as its primary key in `parts.json`. The UUID is
opaque, immutable, and generated automatically on part creation. Users
never interact with UUIDs directly.

Each part also carries a `name` field — a structured, human-readable
string **generated deterministically by the tool** from the part's
structured fields. Users do not write names freeform. The name serves
as the part's identity in the CLI and in KiCad's symbol chooser.

If a part's specs change, the tool regenerates the name. The UUID
stays. KIP can propagate name changes to KiCad references as a
controlled operation.

CLI commands resolve by name:

```bash
kip show RES-10K-1PCT-0603      # resolved to UUID internally
kip alternates add CAP-CER-100n-50V-X7R-0603
```

### 2. Name Generation

The tool generates part names from structured fields using per-category
templates. This ensures consistency — two engineers adding the same
part will always get the same name.

**General format:**

```
CATEGORY[-SUBCATEGORY]-<tier-specific-fields>-PACKAGE
```

**Jellybean names** are derived from key specifications (see §7).
Package is always last — this groups parts by value in KiCad's
alphabetically-sorted symbol chooser (all 10K resistors together,
regardless of package).

**Resistors:**

| Template                                   | Example                  |
|--------------------------------------------|--------------------------|
| `RES-{resistance}-{tolerance}-{package}`   | `RES-10K-1PCT-0603`      |

**Capacitors (per subcategory):**

| Subcat | Template                                                      | Example                      |
|--------|---------------------------------------------------------------|------------------------------|
| `CER`  | `CAP-CER-{capacitance}-{voltage}-{dielectric}-{package}`     | `CAP-CER-100n-50V-X7R-0603` |
| `ELEC` | `CAP-ELEC-{capacitance}-{voltage}-{package}`                 | `CAP-ELEC-100u-25V-10x10`   |
| `TANT` | `CAP-TANT-{capacitance}-{voltage}-{package}`                 | `CAP-TANT-10u-16V-CASEB`    |
| `FILM` | `CAP-FILM-{capacitance}-{voltage}-{package}`                 | `CAP-FILM-100n-100V-7.2x6`  |

**Inductors (per subcategory):**

| Subcat    | Template                                                  | Example                          |
|-----------|-----------------------------------------------------------|----------------------------------|
| (plain)   | `IND-{inductance}-{current_rating}-{package}`             | `IND-10uH-1200mA-0805`          |
| `FERRITE` | `IND-FERRITE-{impedance_100mhz}-{current_rating}-{package}` | `IND-FERRITE-600R-2A-0805`    |
| `CM`      | `IND-CM-{impedance}-{current_rating}-{package}`           | `IND-CM-2200R-500mA-1210`       |
| `CHOKE`   | `IND-CHOKE-{inductance}-{current_rating}-{package}`       | `IND-CHOKE-10uH-3A-12x12`       |

**Diodes (per subcategory):**

| Subcat     | Template                                              | Example                      |
|------------|-------------------------------------------------------|------------------------------|
| (generic)  | `DIO-{Vr}-{If}-{package}`                            | `DIO-100V-1A-SOD123`         |
| `SCHOTTKY` | `DIO-SCHOTTKY-{Vr}-{If}-{package}`                   | `DIO-SCHOTTKY-40V-1A-SOD123` |
| `ZENER`    | `DIO-ZENER-{Vz}-{Pw}-{package}`                      | `DIO-ZENER-3V3-500mW-SOD323` |
| `TVS`      | `DIO-TVS-{Vstandoff}-{Ppeak}-{package}`               | `DIO-TVS-5V-400W-SMA`        |
| `LED`      | `DIO-LED-{colour}-{package}`                          | `DIO-LED-RED-0603`           |

LED colour values include temperature variants for white LEDs:
`WHITE-WARM` (2700K), `WHITE-NEUTRAL` (4000K), `WHITE-COOL` (6500K).

**Crystals:**

| Template                                          | Example                  |
|---------------------------------------------------|--------------------------|
| `XTAL-{frequency}-{load_capacitance}-{package}`  | `XTAL-8MHz-18pF-HC49`   |

**Transistors (per subcategory):**

| Subcat | Template                                      | Example                          |
|--------|-----------------------------------------------|----------------------------------|
| `NMOS` | `TRAN-NMOS-{vds}-{id}-{package}`             | `TRAN-NMOS-30V-5800mA-SOT23`    |
| `PMOS` | `TRAN-PMOS-{vds}-{id}-{package}`             | `TRAN-PMOS-20V-3A-SOT23`        |
| `NPN`  | `TRAN-NPN-{Vceo}-{Ic}-{package}`             | `TRAN-NPN-40V-200mA-SOT23`      |
| `PNP`  | `TRAN-PNP-{Vceo}-{Ic}-{package}`             | `TRAN-PNP-40V-200mA-SOT23`      |

**Fuses:**

| Subcat  | Template                                              | Example                        |
|---------|-------------------------------------------------------|--------------------------------|
| (plain) | `FUSE-{current_rating}-{voltage_rating}-{package}`   | `FUSE-1A-63V-1206`            |
| `PTC`   | `FUSE-PTC-{hold_current}-{voltage_rating}-{package}` | `FUSE-PTC-500mA-16V-0805`     |

**Switches:**

| Template                                    | Example                  |
|---------------------------------------------|--------------------------|
| `SW-{subcat}-{description}-{package}`       | `SW-TACT-6x6-SMD`       |

Switches, relays, and transformers are almost always semi-jellybean or
proprietary and use MPN-based naming (below).

**Test points and fiducials:**

| Category | Template          | Example        |
|----------|-------------------|----------------|
| `TP`     | `TP-{package}`    | `TP-PAD1MM`   |
| `FID`    | `FID-{package}`   | `FID-1MM`     |

**Proprietary names** use the full MPN:

| Category  | Template                                       | Example                          |
|-----------|------------------------------------------------|----------------------------------|
| (any)     | `CATEGORY-{mpn}-{package}`                     | `IC-STM32F405RGT6-LQFP64`       |

**Semi-jellybean names** use the base part number — the generic family
identifier that is consistent across manufacturers and orderable variants
(e.g. `TL072`, not `TL072CDR`). See §6 for the `base_pn` field.

| Category  | Template                                       | Example                          |
|-----------|------------------------------------------------|----------------------------------|
| (any)     | `CATEGORY-{base_pn}-{package}`                 | `IC-TL072-SO8`                   |

**Connectors** are typically proprietary or semi-jellybean. Their names
follow the MPN-based templates above. For the rare jellybean connector
(e.g. a generic pin header), a semi-structured template is used:

| Template                                       | Example                          |
|------------------------------------------------|----------------------------------|
| `CONN-{subcat}-{description}-{package}`        | `CONN-PIN-1x4-254-THT`          |

The `{description}` portion is normalised from structured fields but is
inherently less deterministic than parametric naming. The tool prompts for
a short descriptor and normalises it (uppercase, dashes, standard
abbreviations). Exact consistency is less critical here because connector
identity is typically tied to a specific manufacturer series.

**Conventions:**

- All uppercase except engineering notation values (`10K`, `100n`,
  `4u7`)
- Dashes as separators, no spaces
- Tolerance as integer percentage with `PCT` suffix (`1PCT`, `5PCT`,
  `20PCT`)
- Current: integer amps when the value is a whole number of amps
  (`1A`, `2A`, `3A`); milliamps otherwise (`500mA`, `1200mA`,
  `5800mA`). The `1A2` IEC notation is not used because `A` is a
  unit, not a multiplier
- Power in standard notation (`500mW`, `400W`)
- Impedance with `R` suffix for ohms (`600R`, `2200R`)
- Package as industry standard (`0402`, `SO8`, `LQFP64`, `SOT23-6`)

**Normalisation:**

The tool normalises user input so that two engineers adding the same
part always produce the same name:

- Subcategories: always uppercase (`schottky` → `SCHOTTKY`)
- Engineering values: canonical notation (`4.7kΩ` → `4K7`,
  `0.1µF` → `100n`, `4.7µH` → `4u7`)
- Package codes: normalised via a lookup table of common packages
  (e.g. `SOIC-8` and `SO-8` both normalise to `SO8`; `LQFP-64` →
  `LQFP64`). Unknown packages are uppercased and used as-is.
- The `package` field in the data model stores the human-readable
  form (`LQFP-64`); the name uses the normalised form (`LQFP64`).

The name generation algorithm is implemented in `core/naming.py` and
is the single source of truth. `kip check` validates that all stored
names match what the algorithm would produce from the part's current
fields.

### 3. Categories

Categories are a fixed taxonomy with a short uppercase code used as
the prefix in part names. Subcategories are **freeform strings** — the
table below lists common values but validation does not restrict to
this set. New subcategories appear by first use.

| Code   | Category     | Common subcategories                       | RefDes |
|--------|--------------|--------------------------------------------|--------|
| `RES`  | Resistors    | `NTC`, `PTC`, `ARRAY`, `SHUNT`             | `R`    |
| `CAP`  | Capacitors   | `CER`, `ELEC`, `TANT`, `FILM`             | `C`    |
| `IND`  | Inductors    | `FERRITE`, `CHOKE`, `CM` (common-mode)     | `L`    |
| `DIO`  | Diodes       | `LED`, `ZENER`, `SCHOTTKY`, `TVS`          | `D`    |
| `TRAN` | Transistors  | `NPN`, `PNP`, `NMOS`, `PMOS`, `DUAL`      | `Q`    |
| `IC`   | ICs          | `MCU`, `OPAMP`, `REG`, `LOGIC`, `ADC`,     | `U`    |
|        |              | `DAC`, `SENSOR`, `DRIVER`, `INTERFACE`,    |        |
|        |              | `OPTO`, `COMPARATOR` …                     |        |
| `CONN` | Connectors   | `USB`, `JST`, `PIN`, `TERMINAL`, `RF`      | `J`    |
| `SW`   | Switches     | `TACT`, `SLIDE`, `DIP`, `ROTARY`           | `SW`   |
| `REL`  | Relays       | `SPDT`, `DPDT`, `SSR`                      | `K`    |
| `XTAL` | Crystals     | `OSC` (oscillator)                         | `Y`    |
| `FUSE` | Fuses        | `PTC` (resettable)                         | `F`    |
| `TFRM` | Transformers | —                                          | `T`    |
| `TP`   | Test points  | —                                          | `TP`   |
| `FID`  | Fiducials    | —                                          | `FID`  |
| `MECH` | Mechanical   | `STANDOFF`, `HEATSINK`, `CLIP`             | `H`    |
| `MISC` | Miscellaneous| `VARISTOR`                                 | `U`    |

Each category has a default `RefDes` (reference designator). This is
used as the default when adding a part, but can be overridden per-part.

#### KiCad Library Mapping

Each category maps directly to a KiCad symbol library file generated
by KIP. The part name becomes the symbol name within that library.
A sort-order prefix is applied at generation time for display purposes;
the prefix is not part of the canonical category.

```
Category RES  →  00-Resistors.kicad_sym
                   ├── RES-100R-1PCT-0402
                   ├── RES-10K-1PCT-0603
                   └── RES-4K7-5PCT-0805

Category CAP  →  01-Capacitors.kicad_sym
                   ├── CAP-CER-100n-16V-X7R-0402
                   ├── CAP-CER-100n-50V-X7R-0603
                   └── CAP-ELEC-100u-25V-10x10
```

The `symbol` field in the data model stores the full KiCad reference
(e.g. `00-Resistors:RES-10K-1PCT-0603`). For jellybean passives, KIP
generates both the library entry and the `symbol` field value
automatically — the underlying KiCad symbol is a standard generic
(`Device:R`, `Device:C`, etc.) wrapped in the KIP-managed library.
For ICs and other complex parts, the user links or imports a symbol
and KIP writes it into the appropriate category library.

Because KiCad's symbol chooser sorts alphabetically within a library,
the naming convention's sort order directly affects discoverability.
Package-last naming ensures parts group by value (all 10K resistors
together), not by package (all 0603 parts together).

### 4. Enumerations and Types

Constrained fields use `StrEnum` for type safety, serialisation to
JSON as plain strings, and editor autocompletion.

```python
from enum import StrEnum

class Tier(StrEnum):
    PROPRIETARY = "proprietary"
    SEMI_JELLYBEAN = "semi-jellybean"
    JELLYBEAN = "jellybean"

class Category(StrEnum):
    RES = "RES"
    CAP = "CAP"
    IND = "IND"
    DIO = "DIO"
    TRAN = "TRAN"
    IC = "IC"
    CONN = "CONN"
    SW = "SW"
    REL = "REL"
    XTAL = "XTAL"
    FUSE = "FUSE"
    TFRM = "TFRM"
    TP = "TP"
    FID = "FID"
    MECH = "MECH"
    MISC = "MISC"

class Mounting(StrEnum):
    SMD = "smd"
    THT = "tht"
    OTHER = "other"   # press-fit, chassis-mount, etc.

class RefDes(StrEnum):
    """Reference designator prefixes per IEEE 315 / IEC 60617."""
    R = "R"       # Resistor
    C = "C"       # Capacitor
    L = "L"       # Inductor
    D = "D"       # Diode (including LED)
    Q = "Q"       # Transistor
    U = "U"       # IC
    J = "J"       # Connector
    SW = "SW"     # Switch
    K = "K"       # Relay
    Y = "Y"       # Crystal / oscillator
    F = "F"       # Fuse
    T = "T"       # Transformer
    TP = "TP"     # Test point
    FID = "FID"   # Fiducial
    H = "H"       # Hardware (standoff, screw, etc.)
    FL = "FL"     # Filter
```

**Supplier names** are **not** an enum. They are validated strings
drawn from a configurable set of known suppliers in the project
config. The default set includes `digikey`, `mouser`, `lcsc`,
`farnell`, `newark`, `rs`, `tme`. Users extend this list in their
project configuration without modifying source code.

### 5. Discriminated Union for Part Tiers

The three tiers are modelled as a Pydantic discriminated union on the
`tier` field. This gives per-tier required fields enforced at the type
level and a self-documenting schema via Pydantic's JSON Schema export.

```python
Part = Annotated[
    ProprietaryPart | SemiJellybeanPart | JellybeanPart,
    Discriminator("tier"),
]
```

### 6. Field Specification

#### Common Fields (all tiers)

| Field               | Type                             | Required | Description                                        |
|---------------------|----------------------------------|----------|----------------------------------------------------|
| `name`              | `str`                            | yes      | Tool-generated structured name                     |
| `description`       | `str`                            | yes      | Human-readable description                         |
| `tier`              | `Tier`                           | yes      | `proprietary`, `semi-jellybean`, `jellybean`       |
| `category`          | `Category`                       | yes      | `RES`, `CAP`, `IC`, etc.                           |
| `subcategory`       | `str \| None`                    | no       | Freeform subcategory (`CER`, `MCU`, `LED`, etc.)   |
| `package`           | `str \| None`                    | no       | Package/case (`0402`, `SOIC-8`, `LQFP-64`)         |
| `mounting`          | `Mounting \| None`               | no       | `smd`, `tht`, or `other`                           |
| `datasheet`         | `HttpUrl \| None`                | no       | URL to datasheet (Pydantic `HttpUrl`)              |
| `tags`              | `list[str]`                      | no       | Free-form tags for search                          |
| `notes`             | `str \| None`                    | no       | Free-text notes                                    |
| `symbol`            | `str`                            | yes      | KiCad symbol reference (`Device:R`)                |
| `footprint`         | `str`                            | yes      | KiCad footprint reference (`Resistor_SMD:R_0402…`) |
| `value`             | `str`                            | yes      | Schematic display value (see §8)                   |
| `reference`         | `RefDes`                         | yes      | Reference designator prefix (`R`, `C`, `U`)        |
| `keywords`          | `list[str]`                      | no       | KiCad symbol chooser search terms                  |
| `specifications`    | `dict[str, str] \| None`         | no       | Parametric specs for search/display (see §7)       |
| `exclude_from_bom`  | `bool`                           | no       | Default `false`                                    |
| `exclude_from_board`| `bool`                           | no       | Default `false`                                    |
| `footprint_variant` | `str \| None`                    | no       | Variant suffix for alt footprints (`HS`, `WIDE`)   |
| `suppliers`         | `dict[str, SupplierInfo]`        | no       | Keyed by validated supplier name (see §9)          |

#### Proprietary Fields (tier 1 only)

| Field          | Type   | Required | Description                           |
|----------------|--------|----------|---------------------------------------|
| `mpn`          | `str`  | yes      | Manufacturer part number              |
| `manufacturer` | `str`  | yes      | Manufacturer name                     |

#### Semi-jellybean Fields (tier 2 only)

| Field          | Type              | Required | Description                                    |
|----------------|-------------------|----------|------------------------------------------------|
| `base_pn`      | `str`             | yes      | Generic family part number (`TL072`)           |
| `mpn`          | `str`             | yes      | Preferred specific ordering code (`TL072CDR`)  |
| `manufacturer` | `str`             | yes      | Preferred manufacturer name                    |
| `alternates`   | `list[Alternate]` | no       | Pin-compatible equivalents                     |

`base_pn` is the recognisable family identifier shared across
manufacturers and variants — the part number an engineer would say
aloud (e.g. `TL072`, `LM7805`, `74HC595`). The `mpn` is the specific
manufacturer ordering code. The name uses `base_pn`; supplier data
references `mpn`. For proprietary parts, `base_pn` does not exist
because the `mpn` IS the identity.

#### Jellybean Fields (tier 3 only)

| Field            | Type              | Required | Description                         |
|------------------|-------------------|----------|-------------------------------------|
| `alternates`     | `list[Alternate]` | no       | Known-good specific MPNs            |

The `specifications` field (from common fields) is **required** for
jellybean parts — the discriminated union enforces this. For jellybean
parts, key specs within `specifications` define identity and drive
name generation (see §7). For tier 1/2 parts, `specifications` is
optional and informational — useful for parametric search and display
but not identity-defining.

#### Auto-generated Fields

Several required fields can be generated by the tool, reducing manual
data entry:

- **`name`**: Always generated from structured fields (see §2).
- **`description`**: For jellybean parts, generated from category,
  key specs, and package (e.g. `"10kΩ 1% 0603 thick film resistor"`).
  The user may override at add time, but a sensible default is always
  provided.
- **`value`**: Generated from the primary specification (see §8).
- **`reference`**: Defaults to the category's RefDes (see §3).
- **`symbol`** and **`footprint`**: For jellybean passives, the tool
  provides defaults based on category and package (e.g. `Device:R` +
  `Resistor_SMD:R_0603_1608Metric`). For ICs and other complex parts,
  the user must specify or link these.

### 7. Specifications and Key Specs

All tiers may carry `specifications` — a `dict[str, str]` mapping
parameter names to value strings. Values are strings because component
specifications carry units, tolerances, and qualitative values that
don't reduce to a single numeric type. For tier 1/2 parts, specs are
informational — they enable parametric search ("all MCUs with >1MB
flash", "all opamps with GBW >1MHz") and enriched display. For
jellybean parts, specs are required and define the part.

Each category defines **key specifications** — the parametric fields
that, together with `category`, `subcategory`, and `package`,
constitute part identity for jellybean parts. Two jellybean parts with
identical identity are the same part. `kip add` will refuse to create
a duplicate, and `kip check` will flag it. Supplementary specs provide
additional detail but do not affect identity or deduplication. Key
specs only apply to jellybean parts — they drive name generation and
dedup. Tier 1/2 specs have no key/non-key distinction.

Identity always includes `{category, subcategory}` implicitly — they
are not listed in the per-category tables but are always part of the
identity check. `package` is listed explicitly in each table because
it is a parametric concern (package affects electrical
characteristics). Two parts in different categories or subcategories
are always distinct, even if their parametric key specs happen to
match (e.g. a generic rectifier and a Schottky with the same voltage
and current ratings are different parts because their subcategories
differ).

Per-category conventions define which specification fields are expected.
These conventions are enforced by the tool (`kip add` prompts, `kip
check` validates), not by the schema. Adding a new category never
requires a schema change.

**Resistors (`RES`):**

| Key                       | Key spec | Example        |
|---------------------------|----------|----------------|
| `resistance`              | **yes**  | `"10kΩ"`       |
| `tolerance`               | **yes**  | `"1%"`         |
| `power_rating`            | no       | `"62.5mW"`     |
| `voltage_rating`          | no       | `"50V"`        |
| `temperature_coefficient` | no       | `"±100ppm/°C"` |

Identity: `{resistance, tolerance, package}`

Power rating is not a key spec because it is effectively determined by
package for jellybean chip resistors. A non-standard power rating for
a given package (e.g. 1W 2512 vs 0.5W 2512) indicates a specific part
and belongs in semi-jellybean territory.

**Capacitors — Ceramic (`CAP` / `CER`):**

| Key                | Key spec | Example    |
|--------------------|----------|------------|
| `capacitance`      | **yes**  | `"100nF"`  |
| `tolerance`        | no       | `"±10%"`   |
| `voltage_rating`   | **yes**  | `"50V"`    |
| `dielectric`       | **yes**  | `"X7R"`    |

Identity: `{capacitance, voltage_rating, dielectric, package}`

**Capacitors — Electrolytic (`CAP` / `ELEC`):**

| Key              | Key spec | Example     |
|------------------|----------|-------------|
| `capacitance`    | **yes**  | `"100µF"`   |
| `tolerance`      | no       | `"±20%"`    |
| `voltage_rating` | **yes**  | `"25V"`     |
| `esr`            | no       | `"0.1Ω"`   |
| `ripple_current` | no       | `"250mA"`   |

Identity: `{capacitance, voltage_rating, package}`

**Capacitors — Tantalum (`CAP` / `TANT`):**

| Key              | Key spec | Example     |
|------------------|----------|-------------|
| `capacitance`    | **yes**  | `"10µF"`    |
| `voltage_rating` | **yes**  | `"16V"`     |
| `tolerance`      | no       | `"±20%"`    |
| `esr`            | no       | `"1Ω"`      |

Identity: `{capacitance, voltage_rating, package}`

**Capacitors — Film (`CAP` / `FILM`):**

| Key              | Key spec | Example     |
|------------------|----------|-------------|
| `capacitance`    | **yes**  | `"100nF"`   |
| `voltage_rating` | **yes**  | `"100V"`    |
| `tolerance`      | no       | `"±5%"`     |
| `dielectric`     | no       | `"PET"`     |

Identity: `{capacitance, voltage_rating, package}`

**Inductors (`IND`, plain):**

| Key               | Key spec | Example    |
|-------------------|----------|------------|
| `inductance`      | **yes**  | `"10µH"`   |
| `tolerance`       | no       | `"±20%"`   |
| `current_rating`  | **yes**  | `"1.2A"`   |
| `dcr`             | no       | `"0.15Ω"`  |

Identity: `{inductance, current_rating, package}`

**Ferrite beads (`IND` / `FERRITE`):**

| Key                | Key spec | Example    |
|--------------------|----------|------------|
| `impedance_100mhz` | **yes** | `"600Ω"`   |
| `current_rating`   | **yes** | `"2A"`     |
| `dcr`              | no      | `"0.05Ω"`  |

Identity: `{impedance_100mhz, current_rating, package}`

**Common-mode chokes (`IND` / `CM`):**

| Key               | Key spec | Example    |
|-------------------|----------|------------|
| `impedance`       | **yes**  | `"2200Ω"`  |
| `current_rating`  | **yes**  | `"500mA"`  |
| `num_lines`       | no       | `"2"`      |

Identity: `{impedance, current_rating, package}`

**Power chokes (`IND` / `CHOKE`):**

| Key               | Key spec | Example    |
|-------------------|----------|------------|
| `inductance`      | **yes**  | `"10µH"`   |
| `current_rating`  | **yes**  | `"3A"`     |
| `dcr`             | no       | `"0.03Ω"`  |

Identity: `{inductance, current_rating, package}`

Same identity structure as plain inductors. The subcategory
distinguishes chokes from standard inductors in both name and identity.

**Diodes — generic / rectifier (`DIO`):**

| Key                    | Key spec | Example    |
|------------------------|----------|------------|
| `reverse_voltage`      | **yes**  | `"100V"`   |
| `forward_current`      | **yes**  | `"1A"`     |
| `forward_voltage`      | no       | `"0.7V"`   |
| `reverse_recovery_time`| no       | `"50ns"`   |

Identity: `{reverse_voltage, forward_current, package}`

**Schottky diodes (`DIO` / `SCHOTTKY`):**

| Key                | Key spec | Example    |
|--------------------|----------|------------|
| `reverse_voltage`  | **yes**  | `"40V"`    |
| `forward_current`  | **yes**  | `"1A"`     |
| `forward_voltage`  | no       | `"0.45V"`  |

Identity: `{reverse_voltage, forward_current, package}`

**Zener diodes (`DIO` / `ZENER`):**

| Key              | Key spec | Example     |
|------------------|----------|-------------|
| `zener_voltage`  | **yes**  | `"3.3V"`    |
| `power_rating`   | **yes**  | `"500mW"`   |
| `tolerance`      | no       | `"±5%"`     |

Identity: `{zener_voltage, power_rating, package}`

**TVS diodes (`DIO` / `TVS`):**

| Key               | Key spec | Example     |
|-------------------|----------|-------------|
| `standoff_voltage`| **yes**  | `"5V"`      |
| `peak_power`      | **yes**  | `"400W"`    |
| `clamping_voltage`| no       | `"9.2V"`    |

Identity: `{standoff_voltage, peak_power, package}`

**LEDs (`DIO` / `LED`):**

| Key                 | Key spec | Example         |
|---------------------|----------|-----------------|
| `colour`            | **yes**  | `"red"`         |
| `forward_voltage`   | no       | `"2.0V"`        |
| `forward_current`   | no       | `"20mA"`        |
| `wavelength`        | no       | `"625nm"`       |
| `luminous_intensity`| no       | `"200mcd"`      |

Identity: `{colour, package}`

Colour values include temperature variants for white LEDs:
`warm-white` (2700K), `neutral-white` (4000K), `cool-white` (6500K).
These are not interchangeable in a product — colour temperature
affects appearance and user experience.

**Transistors — MOSFET (`TRAN` / `NMOS` or `PMOS`):**

| Key             | Key spec | Example    |
|-----------------|----------|------------|
| `vds_max`       | **yes**  | `"30V"`    |
| `id_max`        | **yes**  | `"5.8A"`   |
| `rds_on`        | no       | `"28mΩ"`   |
| `vgs_threshold` | no       | `"1.2V"`   |

Identity: `{vds_max, id_max, package}`

**Transistors — BJT (`TRAN` / `NPN` or `PNP`):**

| Key             | Key spec | Example    |
|-----------------|----------|------------|
| `vceo`          | **yes**  | `"40V"`    |
| `ic_max`        | **yes**  | `"200mA"`  |
| `hfe`           | no       | `"200"`    |
| `ft`            | no       | `"300MHz"` |

Identity: `{vceo, ic_max, package}`

Jellybean BJTs are common for simple switching applications ("any
40V 200mA NPN in SOT-23 will do"). For amplifier circuits where hfe
or bandwidth matters, the part is typically semi-jellybean.

**Fuses (`FUSE`):**

| Key               | Key spec | Example    |
|-------------------|----------|------------|
| `current_rating`  | **yes**  | `"1A"`     |
| `voltage_rating`  | **yes**  | `"63V"`    |
| `breaking_capacity`| no      | `"50A"`    |
| `speed`           | no       | `"fast"`   |

Identity: `{current_rating, voltage_rating, package}`

**Resettable fuses (`FUSE` / `PTC`):**

| Key               | Key spec | Example    |
|-------------------|----------|------------|
| `hold_current`    | **yes**  | `"500mA"`  |
| `voltage_rating`  | **yes**  | `"16V"`    |
| `trip_current`    | no       | `"1A"`     |

Identity: `{hold_current, voltage_rating, package}`

**Crystals (`XTAL`):**

| Key               | Key spec | Example     |
|-------------------|----------|-------------|
| `frequency`       | **yes**  | `"8MHz"`    |
| `load_capacitance`| **yes**  | `"18pF"`    |
| `tolerance`       | no       | `"±20ppm"`  |

Identity: `{frequency, load_capacitance, package}`

Load capacitance is a key spec because crystals with different load
capacitance require different matching capacitors on the board. An
8MHz/18pF crystal and an 8MHz/12pF crystal are not interchangeable
on a given PCB — using the wrong one risks oscillator startup failure.

**Deferred categories**: Switches, relays, transformers, connectors,
and mechanical parts are almost always semi-jellybean or proprietary,
so jellybean spec tables for these categories are not yet defined.
If a jellybean use case emerges (e.g. generic tact switches), the
table can be added without schema changes — it is purely a tool-level
convention.

These tables are conventions, not schema constraints. Parts may carry
additional specification fields. Key spec definitions are stored in
`core/naming.py` alongside the name generation templates — the two
are tightly coupled because key specs drive the generated name.

### 8. Value Field Convention

The `value` field is what appears on the KiCad schematic next to the
component. Its content depends on the category:

| Category      | Value convention      | Example                |
|---------------|-----------------------|------------------------|
| `RES`         | Resistance shorthand  | `10k`, `4k7`, `100R`  |
| `CAP`         | Capacitance shorthand | `100n`, `4u7`, `10p`  |
| `IND`         | Inductance shorthand  | `10u`, `100n`         |
| `DIO` (semi)  | MPN                   | `1N4148`, `BAT54`     |
| `DIO` (jelly) | Key specs             | `40V/1A`, `3V3/500mW` |
| `DIO` (LED)   | Colour                | `RED`, `GRN`          |
| `TRAN`        | MPN or generic        | `2N7002`, `BSS138`    |
| `IC`          | MPN                   | `STM32F405RGT6`       |
| `CONN`        | Description           | `USB-C`, `JST-XH-4`   |
| `XTAL`        | Frequency             | `8MHz`                |
| `SW`          | Type                  | `TACT`, `SPDT`        |
| `TP`          | Label                 | `TP`                  |
| `FID`         | Label                 | `FID`                 |

For passives (RES, CAP, IND), the tool generates the value from the
primary specification using KiCad standard notation:

- `k` = kilo, `M` = mega (resistors)
- `n` = nano, `u` = micro, `p` = pico (capacitors, inductors)
- Decimal point replaced with multiplier: `4.7kΩ` → `4k7`
- No units suffix in the value string (KiCad convention)

### 9. Supplier and Alternate Models

```python
class SupplierInfo(BaseModel):
    sku: str                                  # Supplier order code
    url: HttpUrl | None = None                # Product page URL

class Alternate(BaseModel):
    mpn: str                                  # Manufacturer part number
    manufacturer: str                         # Manufacturer name
    notes: str | None = None                  # Why this alternate is suitable
    suppliers: dict[str, SupplierInfo] = {}   # Supplier SKUs for this MPN
```

`SupplierInfo` is deliberately minimal — just `sku` and `url`. Pricing
and stock data are ephemeral (DigiKey stock changes by the minute) and
misleading if manually maintained. When live supplier API integration
is built, pricing and stock will be fetched on demand, not stored in
the parts file.

Supplier names (dict keys in `suppliers`) are validated against a
configurable set of known suppliers (default: `digikey`, `mouser`,
`lcsc`, `farnell`, `newark`, `rs`, `tme`). Users extend this set in
their project configuration without modifying source code.

`alternates` is a list where ordering implies preference — the first
alternate is the most preferred.

#### Supplier Linkage Semantics

Supplier SKUs are always for a specific manufacturer part number.
The `suppliers` field appears at two levels:

- **Part-level `suppliers`**: Refers to the part's primary MPN —
  the `mpn` field for proprietary and semi-jellybean parts. For
  jellybean parts (which have no `mpn`), part-level suppliers is
  a convenience shorthand for the first alternate's suppliers.
- **Alternate-level `suppliers`**: Refers to that specific
  alternate's MPN. This creates an unambiguous MPN→SKU chain
  that BOM resolution can follow.

For jellybean parts, alternate-level suppliers is the canonical
location. A DigiKey SKU `311-10.0KHRCT-ND` is for Yageo
`RC0603FR-0710KL` specifically — it belongs on that alternate, not
floating at the part level. Part-level suppliers on jellybean parts
are permitted but redundant; tools should prefer the canonical
alternate-level form.

### 10. Storage Format

A single `parts.json` file at the root of the kip library:

```json
{
    "version": 1,
    "parts": {
        "f47ac10b-58cc-4372-a567-0e02b2c3d479": {
            "name": "RES-10K-1PCT-0603",
            "tier": "jellybean",
            "description": "10kΩ 1% 0603 thick film resistor",
            "category": "RES",
            "package": "0603",
            "mounting": "smd",
            "symbol": "00-Resistors:RES-10K-1PCT-0603",
            "footprint": "Resistor_SMD:R_0603_1608Metric",
            "value": "10k",
            "reference": "R",
            "specifications": {
                "resistance": "10kΩ",
                "tolerance": "1%",
                "power_rating": "62.5mW"
            },
            "alternates": [
                {
                    "mpn": "RC0603FR-0710KL",
                    "manufacturer": "Yageo",
                    "suppliers": {
                        "digikey": {
                            "sku": "311-10.0KHRCT-ND",
                            "url": "https://www.digikey.com/en/products/detail/…"
                        }
                    }
                }
            ],
            "tags": ["basic", "preferred"]
        },
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
            "name": "IC-STM32F405RGT6-LQFP64",
            "tier": "proprietary",
            "description": "ARM Cortex-M4 MCU, 1MB Flash, 168MHz",
            "category": "IC",
            "subcategory": "MCU",
            "package": "LQFP-64",
            "mounting": "smd",
            "mpn": "STM32F405RGT6",
            "manufacturer": "STMicroelectronics",
            "specifications": {
                "core": "ARM Cortex-M4F",
                "clock": "168MHz",
                "flash": "1MB",
                "ram": "192KB"
            },
            "datasheet": "https://www.st.com/resource/en/datasheet/stm32f405rg.pdf",
            "symbol": "MCU_ST_STM32F4:STM32F405RGTx",
            "footprint": "Package_QFP:LQFP-64_10x10mm_P0.5mm",
            "value": "STM32F405RGT6",
            "reference": "U",
            "suppliers": {
                "digikey": {
                    "sku": "497-17364-ND"
                }
            },
            "tags": ["arm", "cortex-m4"]
        },
        "b2c3d4e5-f6a7-8901-bcde-f12345678901": {
            "name": "IC-TL072-SO8",
            "tier": "semi-jellybean",
            "description": "Dual JFET-input operational amplifier",
            "category": "IC",
            "subcategory": "OPAMP",
            "package": "SO-8",
            "mounting": "smd",
            "base_pn": "TL072",
            "mpn": "TL072CDR",
            "manufacturer": "Texas Instruments",
            "specifications": {
                "channels": "2",
                "gbw": "3MHz",
                "slew_rate": "13V/µs",
                "input_type": "JFET"
            },
            "datasheet": "https://www.ti.com/lit/ds/symlink/tl072.pdf",
            "symbol": "Amplifier_Operational:TL072",
            "footprint": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
            "value": "TL072",
            "reference": "U",
            "alternates": [
                {
                    "mpn": "TL072ACD",
                    "manufacturer": "STMicroelectronics"
                },
                {
                    "mpn": "TL072BCD",
                    "manufacturer": "Onsemi"
                }
            ],
            "tags": ["opamp", "jfet-input", "dual"]
        }
    }
}
```

The `version` field enables future schema migrations. `parts` is a
dictionary keyed by UUID for O(1) lookups and guaranteed uniqueness.

The `name` field is unique across parts and serves as the CLI-facing
identifier. KIP builds an in-memory name→UUID index at load time for
fast resolution.

A single file is appropriate for the expected scale (hundreds to low
thousands of parts). Git diffs remain readable with `indent=2` and
sorted keys. The optional SQLite cache is deferred.

### 11. Footprint Variants

One part = one footprint. A hand-solder variant of the same resistor
(e.g., `R_0603_1608Metric` vs `R_0603_1608Metric_Pad0.9x1mm_HandSolder`)
is a separate library entry. KiCad itself treats each
symbol-footprint pairing as a distinct entity.

Because footprint variants share identical key specs, the standard
name generation would produce a duplicate name. To disambiguate,
parts may carry an optional **footprint variant suffix** appended
to the generated name:

- `RES-10K-1PCT-0603` — standard pads (no suffix)
- `RES-10K-1PCT-0603-HS` — hand-solder pads

Common suffixes: `-HS` (hand-solder), `-WIDE` (extended pads). The
suffix is freeform, becomes part of the stored name, and is included
in the identity check (so the two entries are distinct).

The first entry for a given identity has no suffix. Subsequent
footprint variants require a suffix. `kip add` detects the collision
and prompts for a variant tag.

This keeps the model simple. The alternative (a list of footprints per
part with a primary) adds complexity for an edge case that is better
handled as "add another part with a variant tag."

## Consequences

### Positive

- **Stable identity**: UUIDs are globally unique, trivial to generate,
  and never collide. External references via UUID survive any rename or
  reclassification.
- **Consistent naming**: Tool-generated names eliminate inconsistency.
  Two engineers adding the same 10K 1% 0402 resistor get the same name
  — and the tool detects the duplicate via key spec matching.
- **Safe renames**: Changing a part's specs regenerates the name. The
  UUID key is untouched. KIP can propagate name changes to KiCad config
  as a controlled operation.
- **Type safety**: Discriminated union catches invalid data at parse
  time. A proprietary part without an MPN fails validation immediately.
  Enums prevent typos in categories, mounting types, and reference
  designators.
- **Schema flexibility**: New component categories, subcategories, and
  specification fields don't require code changes. Per-category
  conventions are a tool-level concern.
- **Git-friendly**: JSON with sorted keys and consistent indentation
  produces clean, reviewable diffs.
- **KiCad-ready fields**: Parts carry everything KiCad's HTTP library
  API expects.
- **Lean supplier data**: Only sku and url are stored. No stale pricing
  or stock numbers misleading users.
- **Parametric search across all tiers**: Specifications on all tiers
  enable queries like "all MCUs with >1MB flash" without relying on
  unstructured tags or descriptions.
- **Unambiguous supplier linkage**: Supplier SKUs on alternates create
  a traceable MPN→SKU chain for BOM resolution.

### Negative

- **No parametric type safety**: Specification values are strings, so
  `"resistance": "banana"` is valid at the schema level. Validation
  must happen at the tool level (`kip add`, `kip check`).
- **Name uniqueness enforcement**: The name is unique but not the key,
  so uniqueness must be enforced by the CRUD layer rather than by the
  data structure.
- **Single file scaling**: At thousands of parts, `parts.json` gets
  large. A split-by-category approach could help but adds complexity.
- **UUID readability**: JSON diffs show UUIDs as keys, which are not
  human-readable. The `name` field on the next line provides context,
  but it's noisier than a structured key.
- **One footprint per part**: Footprint variants require separate
  entries with a variant suffix, which may feel redundant for parts
  that differ only in land pattern.
- **Tier 1/2 spec field names are unstandardised**: One user writes
  `clock`, another writes `frequency`. Acceptable because tier 1/2
  specs are informational, not identity-defining. Tool-level
  conventions (prompted by `kip add`) encourage consistency.

### Neutral

- **Alternates on proprietary parts**: Currently excluded by the model.
  If needed, `ProprietaryPart` can grow an alternates field without
  breaking existing data.
- **HTTP library integration**: The model carries all fields KiCad's
  HTTP library API requires. Implementation deferred but the data
  model is ready.
- **Supplier data expansion**: When live API integration is built,
  `SupplierInfo` can grow pricing and stock fields without breaking
  existing data (new optional fields).
- **Category sort prefixes**: Applied at KiCad config generation time,
  not stored on parts. The canonical category is `RES`, the display
  name in KiCad might be `00-Resistors`.

## Implementation Notes

### Files to Create

```
src/kip/
├── models/
│   ├── __init__.py      # Re-export Part, Supplier, Alternate, enums
│   └── part.py          # All models and enums
└── core/
    ├── __init__.py
    ├── database.py      # JSON CRUD: load, save, add, remove, get, list
    ├── naming.py        # Name generation, key spec definitions, identity
    └── kicad.py         # KiCad library generation (.kicad_sym output)
```

### UUID Generation

```python
import uuid

def generate_id() -> str:
    return str(uuid.uuid4())
```

### Name Resolution

At load time, build an in-memory index:

```python
name_index: dict[str, str] = {
    part.name: uid for uid, part in parts.items()
}
```

### JSON Round-Trip

```python
def load(path: Path) -> dict[str, Part]:
    data = json.loads(path.read_text())
    return {
        uid: TypeAdapter(Part).validate_python(part_data)
        for uid, part_data in data["parts"].items()
    }

def save(path: Path, parts: dict[str, Part]) -> None:
    data = {
        "version": 1,
        "parts": {
            uid: part.model_dump(mode="json", exclude_none=True)
            for uid, part in sorted(parts.items(), key=lambda p: p[1].name)
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
```

Sorting by `name` (not UUID) ensures deterministic, human-scannable
output and clean diffs. Parts sort alphabetically by category (`CAP-*`
before `CONN-*` before `DIO-*`), which is a reasonable default.
