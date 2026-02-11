# ADR-002: KiCad Integration

**Status**: Draft
**Date**: 2026-02-10
**Supersedes**: ADR-001 §KiCad Library Mapping (refines prefix convention
from `00-Resistors` to `00k-Resistors`; this ADR is authoritative for all
KiCad integration details)

## Context

Kist exists to formalise the concept of a personal or team component
library — symbols, footprints, 3D models, and part metadata — as a
single Git-trackable artifact. The library lives in its own repository
and is added as a **Git submodule** to each KiCad project that uses it.
This is why the data model uses plain-text JSON: it must diff cleanly,
merge sensibly, and travel with Git.

KiCad needs to discover the library's symbols, footprints, and part
metadata through its native mechanisms. The integration must work
without requiring the user to run a server or maintain configuration
outside the submodule.

### KiCad's Library Mechanisms

1. **Native symbol and footprint files** — KiCad stores schematic
   symbols in `.kicad_sym` files and footprints in `.kicad_mod` files
   within `.pretty` directories. Both formats use KiCad's text-based
   S-expression syntax. Projects reference these files through
   `sym-lib-table` and `fp-lib-table` lookup tables. No external
   dependencies.

2. **HTTP libraries (`.kicad_httplib`)** — KiCad 8+ can fetch part
   data from a REST API at symbol-chooser time, allowing dynamic
   metadata (pricing, stock, parametric search) without pre-generated
   files. Requires a running server. See the [KiCad HTTP library
   docs][1] for the API specification.

[1]: https://dev-docs.kicad.org/en/apis-and-binding/http-libraries/

### KiCad CLI

KiCad ships `kicad-cli` with a `sch export bom` command that extracts
a BOM from a schematic with configurable field selection. The CLI can
also export BOM data as XML via `sch export python-bom`, which
provides a structured intermediate representation. Kist can use either
as the input for its BOM resolution workflow: extract the placed
components and their Kist part names from the schematic, then resolve
each to a specific MPN and supplier SKU using the alternates and
supplier data in `parts.json`. This bridges the gap between "I placed
a `RES-10K-1PCT-0603` on the schematic" and "order Yageo
`RC0603FR-0710KL` from DigiKey."

### Requirements

- The library must work as a Git submodule with zero external
  dependencies (no servers, no special drivers).
- Symbols and footprints must be standard KiCad files that the
  schematic and board editors can open directly.
- Part metadata from `parts.json` (value, reference, datasheet,
  supplier info, custom fields) must flow into KiCad symbols so that
  placed components carry the right data.
- Adding or modifying a part in Kist should update the KiCad-facing
  files automatically.
- The symbol chooser should present parts grouped by category and
  sorted by value, not by UUID or insertion order.

## Decision

### 1. Library Directory Structure

A Kist library is a self-contained directory (and Git repository) with
this layout:

```
my-library/
├── parts.json                    # Source of truth (ADR-001)
├── symbols/
│   ├── 00k-Resistors.kicad_sym
│   ├── 01k-Capacitors.kicad_sym
│   ├── ...
│   └── 15k-Misc.kicad_sym
├── footprints/
│   ├── 00k-Resistor-SMD.pretty/
│   │   └── R_0603_1608Metric.kicad_mod
│   ├── 00k-Package-QFP.pretty/
│   │   └── LQFP-64_10x10mm_P0.5mm.kicad_mod
│   └── ...
├── 3dmodels/
│   ├── R_0603.step
│   ├── LQFP-64.step
│   └── ...
├── blocks/                       # Design block libraries (KiCad 9+)
│   └── 00k-Power-Supply.kicad_blocks/
│       └── LDO-3V3.kicad_block/
│           ├── LDO-3V3.json      #   metadata (description, keywords)
│           └── LDO-3V3.kicad_sch #   schematic fragment
└── .kist/
    └── config.toml               # Library configuration (ADR-003)
```

### 2. Native `.kicad_sym` Files — No Database Layer

The integration uses **native KiCad symbol libraries only**. No
`.kicad_httplib`, no server.

Kist manages one `.kicad_sym` file per category. Each part in
`parts.json` has a corresponding symbol entry in the appropriate
category library. The symbol entry carries all KiCad-relevant metadata
as properties: `value`, `reference`, `footprint`, `datasheet`,
`keywords`, `description`, `exclude_from_bom`, `exclude_from_board`.

The user creates symbols — either by drawing them in KiCad's symbol
editor, importing from SnapEDA, or having kist generate a stub (see
§3). Kist manages the library file structure: it places symbols into
the correct category library and writes metadata properties from
`parts.json` onto each symbol via `kist sync`.

This approach:

- Works with any KiCad 9+ installation out of the box.
- Requires no tooling at schematic-open time — the `.kicad_sym` files
  are standard KiCad files.
- Diffs cleanly in Git (KiCad's S-expression format is text-based).
- Means the library submodule is fully self-contained.

The tradeoff is that `kist sync` must parse and update the
`.kicad_sym` files whenever `parts.json` changes — patching metadata
onto existing symbols rather than regenerating from scratch. This is
a manual step for now (invoked explicitly or by mutation commands like
`kist add`).

### 3. Symbol Creation

Kist uses a **tiered approach** to symbol creation:

**Jellybean passives** (resistors, capacitors, inductors, simple
diodes): Kist generates complete, self-contained symbol entries. A
`RES-10K-1PCT-0603` entry in `00k-Resistors.kicad_sym` contains the
full graphical body (zigzag for resistors, plates for capacitors, etc.)
with Kist-managed properties (value, footprint, description, etc.)
baked in. The user never creates these symbols manually.

Kist ships built-in graphical templates for common passive body shapes.
On first use (or via `kist init`), kist can also extract symbol
graphics from the local KiCad installation's standard libraries
(`Device:R`, `Device:C`, etc.) to stay consistent with the user's
KiCad version. The extracted graphics are cached in `.kist/` and used
as templates for all future symbol generation.

**ICs and complex parts**: Kist creates a **placeholder symbol stub**
in the appropriate category library with all metadata properties and
pin declarations but no graphical layout. The user then opens the
symbol in KiCad's symbol editor to arrange pins and draw the body.
This separates the tedious data entry (pin names, numbers, types)
from the creative layout work.

Symbols can also be imported from external sources (SnapEDA,
UltraLibrarian, hand-drawn) — kist places them into the category
library and writes metadata properties onto them.

The `.kicad_sym` file is the final artifact that KiCad reads. The
user owns the symbol content (graphical layout, pin arrangement).
Kist owns the library file structure and the metadata properties
written onto each symbol.

### 4. Category-to-Library Mapping

Each `Category` enum value maps to one `.kicad_sym` file with a
numeric sort prefix and `k` infix:

| Prefix | Library file               | Category |
|--------|----------------------------|----------|
| `00k`  | `00k-Resistors.kicad_sym`  | `RES`    |
| `01k`  | `01k-Capacitors.kicad_sym` | `CAP`    |
| `02k`  | `02k-Inductors.kicad_sym`  | `IND`    |
| `03k`  | `03k-Diodes.kicad_sym`     | `DIO`    |
| `04k`  | `04k-Transistors.kicad_sym`| `TRAN`   |
| `05k`  | `05k-ICs.kicad_sym`        | `IC`     |
| `06k`  | `06k-Connectors.kicad_sym` | `CONN`   |
| `07k`  | `07k-Switches.kicad_sym`   | `SW`     |
| `08k`  | `08k-Relays.kicad_sym`     | `REL`    |
| `09k`  | `09k-Crystals.kicad_sym`   | `XTAL`   |
| `10k`  | `10k-Fuses.kicad_sym`      | `FUSE`   |
| `11k`  | `11k-Transformers.kicad_sym`| `TFRM`  |
| `12k`  | `12k-TestPoints.kicad_sym` | `TP`     |
| `13k`  | `13k-Fiducials.kicad_sym`  | `FID`    |
| `14k`  | `14k-Mechanical.kicad_sym` | `MECH`   |
| `15k`  | `15k-Misc.kicad_sym`       | `MISC`   |

The 16 categories are a **fixed, opinionated set** owned by kist,
matching the `Category` enum from ADR-001. Users cannot add arbitrary
categories. This is a deliberate design choice — a fixed taxonomy
keeps the library structure predictable and the tooling simple. The
`MISC` category exists as a catch-all. If a genuinely new category
emerges, it is added to the enum (a code change), not configured per
library.

The numeric prefix controls sort order in KiCad's symbol chooser.
Each library file contains all parts for that category — the result
in KiCad's symbol chooser looks like:

```
Symbol Chooser
├── 00k-Resistors
│   ├── RES-100R-1PCT-0402
│   ├── RES-10K-1PCT-0603
│   └── RES-4K7-5PCT-0805
├── 01k-Capacitors
│   ├── CAP-CER-100n-16V-X7R-0402
│   └── CAP-CER-100n-50V-X7R-0603
├── 05k-ICs
│   ├── IC-STM32F405RGT6-LQFP64
│   └── IC-TL072-SO8
...
```

Within each library, symbols sort alphabetically by part name. Because
ADR-001's naming convention puts package last, parts group by value
(all 10K resistors together) rather than by package.

The prefix is a display concern only — it is not stored in
`parts.json`. The mapping from `Category` to prefix is defined in
`core/kicad.py`.

### 5. Design Blocks

Design blocks (KiCad 9+) are reusable schematic fragments — a
complete sub-circuit (e.g. LDO with decoupling caps, USB-C with ESD
protection) that can be placed into any schematic as inline content
or as a hierarchical sheet. Implementation is deferred to a later
milestone, but the on-disk layout and discovery mechanism are
documented here so that the directory structure is stable from
`kist init`.

Kist stores design blocks in the library alongside symbols and
footprints. The on-disk structure follows KiCad's native format:

```
blocks/
  00k-Power-Supply.kicad_blocks/  <- design block library
    npm1300.kicad_block/          <- individual block (directory)
      npm1300.json                <- metadata: description, keywords
      npm1300.kicad_sch           <- schematic fragment
```

Design blocks reference kist-managed symbols (e.g.
`00k-Resistors:RES-10K-1PCT-0603`). As long as the project's
`sym-lib-table` includes the kist symbol libraries, design blocks
resolve correctly.

KiCad discovers design blocks through a `design-block-lib-table` at
the project root, structured identically to `sym-lib-table` and
`fp-lib-table`:

```
(design_block_lib_table
  (version 7)
  (lib (name "00k-Power-Supply")(type "KiCad")(uri "${KIPRJMOD}/lib/blocks/00k-Power-Supply.kicad_blocks")(options "")(descr ""))
)
```

`kist sync` manages this table alongside the symbol and footprint
tables, using the same `${KIPRJMOD}/lib/` convention and `k`-infix
naming for kist-owned entries.

The `blocks/` directory name is configurable via `.kist/config.toml`
(`blocks_dir`), consistent with the other directory settings.

### 6. Footprint and 3D Model Storage

Footprints are standard `.kicad_mod` files organised in `.pretty`
directories under `footprints/`. Kist does not generate footprints — it
stores them. Users add footprints by:

- Copying from KiCad's standard libraries
- Importing from SnapEDA / UltraLibrarian
- Drawing in KiCad's footprint editor and saving into the library

3D models (`.step`, `.wrl`) live under `3dmodels/`.

The `footprint` field in `parts.json` stores the full library
reference (e.g. `00k-Resistor-SMD:R_0603_1608Metric`), where
`00k-Resistor-SMD` maps to the `footprints/00k-Resistor-SMD.pretty/`
directory. All footprint directories use the `00k` prefix — there is
no meaningful ordering between them, but the numeric prefix sorts
kist-managed entries before user or KiCad standard entries.
Footprint filenames within the directory are kept as-is from their
source (KiCad standard libraries, SnapEDA, etc.).

### 7. Path Convention — `${KIPRJMOD}/lib/`

The library is always at `lib/` relative to the KiCad project root.
This is an opinionated convention that makes `git clone` just work —
no KiCad configuration, no custom path variables, no kist installation
required to open a project.

All kist-managed paths use `${KIPRJMOD}/lib/`:

- 3D model refs in footprints: `${KIPRJMOD}/lib/3dmodels/R_0603.step`
- Symbol lib table entries: `${KIPRJMOD}/lib/symbols/00k-Resistors.kicad_sym`
- Footprint lib table entries: `${KIPRJMOD}/lib/footprints/00k-Resistor-SMD.pretty`

`KIPRJMOD` is KiCad's built-in path variable — it always resolves to
the current project's absolute path, is set automatically, and cannot
be overridden. The directory names (`symbols`, `footprints`,
`3dmodels`) come from `.kist/config.toml`.

#### Single-board project

The library is a Git submodule (for distribution) or committed
directly:

```
project/
  lib/                    <- submodule or committed
    .kist/config.toml
    parts.json
    symbols/
    footprints/
    3dmodels/
    blocks/
  project.kicad_pro
  sym-lib-table
  fp-lib-table
  design-block-lib-table
```

`git clone --recurse-submodules`, open KiCad, everything resolves.

#### Multi-board project

Multiple KiCad projects share one library. Each project directory
has a symlink (or directory junction on Windows) to the shared
library, so `${KIPRJMOD}/lib/` resolves correctly for all of them:

```
root/
  lib/                    <- actual library
  board-a/
    lib -> ../lib         <- symlink / junction
    board-a.kicad_pro
  board-b/
    lib -> ../lib         <- symlink / junction
    board-b.kicad_pro
```

`kist init --link` creates these links cross-platform — symlinks on
Unix, directory junctions (`mklink /J`) on Windows. Directory
junctions do not require elevated privileges or developer mode,
unlike symbolic links on Windows. Each project's `sym-lib-table`
and `fp-lib-table` use the same `${KIPRJMOD}/lib/...` paths.

#### Path validation and directory renames

The directory names embedded in KiCad paths (`symbols`, `footprints`,
`3dmodels`) come from `.kist/config.toml`. If a user changes a
directory name in the config (e.g. `symbols_dir = "sym"`), all paths
referencing the old name break:

- Lib table entries (`sym-lib-table`, `fp-lib-table`)
- 3D model references inside `.kicad_mod` footprint files
- The physical directory on disk

`kist check` validates that all paths resolve — lib table entries,
3D model references in footprints, symbol references in `parts.json`.
It detects config/path mismatches and reports them.

`kist sync` rewrites affected paths to match the current config.
For 3D model references, this means parsing and updating every
`.kicad_mod` file in the footprints directory — an infrequent but
potentially expensive operation. The user is responsible for
renaming the actual directory; kist will not move files silently.

In practice, directory names are set once at `kist init` and never
changed. This is an edge case, but the tooling should handle it
gracefully rather than leaving the library in a broken state.

### 8. Project Integration

A KiCad project's `sym-lib-table` and `fp-lib-table` reference the
library at `${KIPRJMOD}/lib/`:

```
(sym_lib_table
  (version 7)
  (lib (name "00k-Resistors")(type "KiCad")(uri "${KIPRJMOD}/lib/symbols/00k-Resistors.kicad_sym")(options "")(descr ""))
  (lib (name "01k-Capacitors")(type "KiCad")(uri "${KIPRJMOD}/lib/symbols/01k-Capacitors.kicad_sym")(options "")(descr ""))
  ...
)
```

```
(fp_lib_table
  (version 7)
  (lib (name "00k-Resistor-SMD")(type "KiCad")(uri "${KIPRJMOD}/lib/footprints/00k-Resistor-SMD.pretty")(options "")(descr ""))
  (lib (name "00k-Package-QFP")(type "KiCad")(uri "${KIPRJMOD}/lib/footprints/00k-Package-QFP.pretty")(options "")(descr ""))
  ...
)
```

Footprint `.pretty` directories are organised by package type (not by
component category) because footprints are shared across categories —
a single `R_0603_1608Metric` footprint serves resistors, capacitors,
and LEDs.

Kist must handle **existing** table files — most projects already have
`sym-lib-table` and `fp-lib-table` with entries for KiCad's standard
libraries or other custom libraries. The workflow is:

1. User has an existing KiCad project with existing table files.
2. User adds the kist library (via submodule, symlink, or path).
3. User runs a kist command to update the table files.
4. Kist parses the existing tables, appends/updates kist-managed
   entries, and writes the file back — preserving all non-kist entries.

Kist-managed entries are identified by the `k` infix in the numeric
prefix (`00k-Resistors`, `01k-Capacitors`, `00k-Resistor-SMD`, etc.).
The `k` makes kist entries trivially distinguishable from user-managed
or KiCad standard entries. Kist only touches entries matching this
naming convention, leaving everything else intact.

`kist sync` updates these table files when categories are added,
footprint directories change, or the library path changes.

### 9. The `kist sync` Command

After any change to `parts.json`, the user runs:

```bash
kist sync
```

This synchronises the `.kicad_sym` files with `parts.json`. The
operation is idempotent — running it twice produces the same result.
Both `parts.json` and the symbol files are committed to Git.

`kist sync` is also invoked implicitly by mutation commands (`kist add`,
`kist edit`, `kist remove`) so that the KiCad files stay consistent.

Specifically, `kist sync`:

1. Reads `parts.json` and `.kist/config.toml`.
2. Groups parts by category.
3. For each category library file:
   a. For jellybean passives, generates symbol entries from standard
      templates (resistor zigzag, capacitor plates, etc.).
   b. For ICs and complex parts, preserves existing symbol content
      (pin layout, graphics) and updates only metadata properties.
4. Writes the files to the configured symbols directory.
5. Updates `sym-lib-table`, `fp-lib-table`, and
   `design-block-lib-table` if present, using directory names from
   config.
6. Rewrites 3D model paths in `.kicad_mod` files if the configured
   models directory has changed.

Error handling for partial sync failures is TBD — e.g. whether a
parse failure in one `.kicad_sym` file should abort the entire sync
or skip and continue.

This requires S-expression parsing at three levels of fidelity:

- **`.kicad_sym` files**: Full round-trip parser that preserves
  user-drawn graphics (lines, arcs, pin positions) while allowing
  metadata property updates. This is the primary implementation
  effort.
- **Lib table files** (`sym-lib-table`, `fp-lib-table`,
  `design-block-lib-table`): Simple, flat S-expression structures.
  Minimal parsing complexity.
- **`.kicad_mod` files**: Targeted rewriting for 3D model path
  strings (`(model "..." ...)`). Does not require semantic
  understanding of footprint geometry — a tokenizer that locates
  and updates model path strings suffices.

Kist will implement its own parser from the KiCad file format
specification (existing libraries like kiutils are GPL-licensed and
unmaintained).

### 10. Future: HTTP Library API & Daemon

The native-file approach is the v1 integration. Future possibilities:

**`kist serve`** — expose `parts.json` as a KiCad HTTP library
(`.kicad_httplib`). This would enable live parametric search in
KiCad's symbol chooser, on-demand loading without pre-generated
`.kicad_sym` files, and dynamic metadata (pricing, stock) at
place-component time.

**`kistd`** — a daemon that watches `parts.json` for changes and
auto-runs sync, combines the HTTP library API with a file watcher
so that KiCad always sees the latest library state.

Both are additive — the native-file approach remains the primary and
offline-capable integration path.

## Consequences

### Positive

- **Zero dependencies**: A cloned submodule works immediately. No
  running servers, no Python runtime needed at KiCad time.
- **Git-native**: Both `parts.json` and `.kicad_sym` files are
  committed. The library is fully versioned and reproducible.
- **Portable**: The submodule pattern means any KiCad project on any
  machine can use the library by cloning with `--recurse-submodules`.
- **Offline**: No network access needed to open schematics or place
  components.
- **Standard KiCad workflow**: Engineers interact with the library
  through KiCad's normal symbol chooser. No custom plugins or
  workflows needed at schematic capture time.

### Negative

- **Generated files in Git**: The `.kicad_sym` files are derived from
  `parts.json` but committed alongside it. This creates potential for
  drift if someone edits a `.kicad_sym` file directly. `kist check`
  should detect metadata property drift (fields that kist owns), but
  must not flag changes to symbol graphics (lines, arcs, pin layout)
  which are user-owned content that kist stores but does not generate
  (except for jellybean passives).
- **Sync step**: Every `parts.json` change requires `kist sync`
  (though mutation commands invoke it automatically). Forgetting to
  sync after a manual JSON edit leaves files inconsistent.
- **S-expression round-tripping**: Kist must parse and faithfully
  reproduce KiCad's S-expression format to update symbol metadata
  without disturbing user-drawn graphics. This requires a custom
  parser built from the KiCad file format docs.
- **Library table maintenance**: Adding a new category (rare) requires
  updating the project's `sym-lib-table`. `kist sync` can detect and
  warn about this.

### Neutral

- **HTTP library is deferred**: The `.kicad_httplib` path is a future
  enhancement. The native-file approach covers all v1 use cases.
- **Footprint organisation**: Footprint `.pretty` directories are
  organised by package type with a `00k-` prefix. Users choose
  directory groupings (mirroring KiCad's standard layout or their
  own) and kist manages the `fp-lib-table` entries. The `footprint`
  field in `parts.json` is the reference of record.
