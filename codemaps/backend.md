# Backend

> Freshness: 2026-02-23

## CLI Module (`src/kist/cli/`)

### app.py (214 lines)

Typer application with callback + subcommands.

| Export | Line | Description |
|---|---|---|
| `app` | :9 | Typer instance, `invoke_without_command=True` |
| `main()` | :18 | Callback: `--version` flag, launches TUI if no subcommand |
| `init()` | :35 | Create library: delegates to `core.library.init_library` |
| `link()` | :82 | Link project to library: delegates to `core.library.link_library` |
| `add()` | :101 | Add a part to the library |
| `search()` | :111 | Search for parts, display as Rich table |
| `check()` | :149 | Validate part names, check for duplicate identities |
| `sync()` | :189 | Sync KiCad symbol files and lib tables with parts database |

Imports are deferred inside command bodies to keep CLI startup fast.

## Core Module (`src/kist/core/`)

### config.py (169 lines)

Configuration I/O using tomlkit for round-trip TOML.

| Export | Line | Description |
|---|---|---|
| `KIST_MARKER` | :16 | `".kist"` directory name |
| `PROJECT_REF` | :17 | `"kist.toml"` filename |
| `LIBRARY_CONFIG` | :18 | `"config.toml"` filename |
| `load_global_config()` | :29 | Read global config, defaults if absent |
| `save_global_config()` | :41 | Write global config to user config directory |
| `resolve_init_config()` | :50 | Merge defaults + global + CLI overrides |
| `load_library_config()` | :60 | Read `.kist/config.toml` |
| `save_library_config()` | :96 | Write `.kist/config.toml` |
| `load_project_ref()` | :106 | Read `kist.toml` project ref |
| `save_project_ref()` | :117 | Write `kist.toml` project ref |
| `load_provider_mapping()` | :131 | Load provider mapping, merging user TOML over defaults |

Config dir: `KIST_CONFIG_DIR` env var, or `platformdirs.user_config_dir("kist")`.

### database.py (147 lines)

JSON-backed parts database with CRUD operations.

| Export | Line | Description |
|---|---|---|
| `create_empty()` | :20 | Write empty `parts.json` |
| `PartsDatabase` | :26 | Main CRUD class |
| `.load()` | :50 | Deserialize from JSON |
| `.save()` | :66 | Serialize to JSON (sorted by name) |
| `.add()` | :86 | Add part, auto-generate UUID IPN |
| `.remove()` | :102 | Remove by IPN |
| `.get()` | :110 | Lookup by IPN |
| `.resolve()` | :114 | Name --> IPN lookup |
| `.list_parts()` | :118 | All parts sorted by name |
| `.search()` | :122 | Substring search across fields |

Uses `pydantic.TypeAdapter` for the `Part` discriminated union (type alias, not BaseModel).

### library.py (198 lines)

Library lifecycle: create, link, discover.

| Export | Line | Description |
|---|---|---|
| `DiscoveryResult` | :27 | NamedTuple(library_root, project_dir=None) |
| `init_library()` | :34 | Create `.kist/`, `config.toml`, `parts.json`, asset dirs |
| `link_library()` | :87 | Create `kist.toml` + `lib/` symlink/junction |
| `find_library()` | :140 | Walk-up discovery from start dir to filesystem root |

`_create_lib_link()` (:109) handles symlink (Unix) vs junction (Windows).
`_find_project_for_library()` (:174) checks parent for kist.toml pointing back to library root.

### naming.py (665 lines)

Engineering value normalisation, canonical name generation, and part identity.

**Normalisers** (all `str --> str`):

| Function | Line | Example |
|---|---|---|
| `normalise_resistance()` | :186 | `"4.7kΩ"` --> `"4K7"` |
| `normalise_capacitance()` | :199 | `"0.1µF"` --> `"100n"` |
| `normalise_inductance()` | :211 | `"10µH"` --> `"10u"` |
| `normalise_voltage()` | :221 | `"3.3V"` --> `"3V3"` |
| `normalise_current()` | :241 | `"500mA"` --> `"500mA"` |
| `normalise_power()` | :262 | `"500mW"` --> `"500mW"` |
| `normalise_frequency()` | :283 | `"8MHz"` --> `"8MHz"` |
| `normalise_percentage()` | :319 | `"1%"` --> `"1PCT"` |
| `normalise_impedance()` | :334 | `"600Ω"` --> `"600R"` |
| `normalise_package()` | :355 | `"SOIC-8"` --> `"SO8"` |

**Generators**:

| Function | Line | Description |
|---|---|---|
| `generate_name()` | :488 | Canonical part name from structured fields (ADR-001 §2) |
| `generate_value()` | :548 | Schematic display value (ADR-001 §8) |
| `generate_description()` | :595 | Human-readable description |
| `get_identity()` | :636 | Deduplication tuple (ADR-001 §7) |

**Key data structures**:

| Constant | Line | Description |
|---|---|---|
| `SPEC_NORMALISERS` | :379 | `spec_field_name --> normaliser function` |
| `_SI_PREFIXES` | :19 | SI prefix letter --> multiplier |
| `_PACKAGE_ALIASES` | :53 | Common package name aliases |

Internal: `_parse_engineering()` (:99) parses any engineering value string. `_format_eng_rlc()` (:144) formats float back to shorthand.

### categories.py (134 lines)

Built-in category definitions.

| Export | Line | Description |
|---|---|---|
| `WELL_KNOWN_CATEGORIES` | :7 | Dict of CategoryDef for all 16 built-in categories (RES..MISC) |

### check.py (60 lines)

Library validation.

| Export | Line | Description |
|---|---|---|
| `CheckIssue` | :13 | Dataclass: kind, message, parts |
| `check_library()` | :22 | Validate part names and check for identity duplicates |

Issue kinds: `name_drift` (generated name != stored name), `duplicate_identity`.

### sync.py (106 lines)

Push part metadata to KiCad files.

| Export | Line | Description |
|---|---|---|
| `SYM_LIB_TABLE` | :15 | `"sym-lib-table"` filename |
| `sync_symbols()` | :18 | Write .kicad_sym per category from PartsDatabase |
| `sync_sym_lib_table()` | :75 | Write/update sym-lib-table in project dir |

## KiCad Module (`src/kist/kicad/`)

### sexpr.py (485 lines, at `src/kist/sexpr.py`)

Standalone S-expression parser/serializer for KiCad v8 file format.

| Export | Line | Description |
|---|---|---|
| `SexprError` | :58 | Parse/serialization exception |
| `Atom` | :65 | Token that remembers source quoting (quoted: bool) |
| `SExpr` | :92 | Type alias: `str \| list["SExpr"]` |
| `tokenize()` | :153 | Generator yielding tokens from S-expr text |
| `parse()` | :223 | Parse text, return all top-level forms |
| `parse_one()` | :261 | Parse expecting exactly one top-level form |
| `find_all()` | :277 | Direct children of expr with matching tag |
| `find_one()` | :284 | First direct child with tag, or None |
| `set_child()` | :292 | Replace/append child with tag |
| `remove_children()` | :303 | Remove all children with tag |
| `dumps()` | :478 | Format S-expr tree using KiCad v8 conventions |

### symbols.py (180 lines)

In-memory .kicad_sym file abstraction.

| Export | Line | Description |
|---|---|---|
| `SymbolLibrary` | :27 | Load, manipulate, save .kicad_sym files |
| `.load()` | :41 | Parse from file |
| `.empty()` | :50 | Fresh library with version/generator metadata |
| `.save()` | :62 | Write to file |
| `.symbols()` | :68 | List symbol names |
| `.get_symbol()` | :72 | Get symbol S-expr subtree |
| `.set_symbol()` | :79 | Add/replace symbol |
| `.remove_symbol()` | :93 | Remove symbol by name |
| `.update_properties()` | :109 | Patch property values on symbol |
| `get_visible_properties()` | :168 | Find non-hidden properties on symbol |

### templates.py (527 lines)

Symbol tree builders dispatched by category/template.

| Export | Line | Description |
|---|---|---|
| `build_properties()` | :78 | Extract KiCad property values from Part model |
| `resistor_symbol_iec()` | :100 | IEC rectangle resistor symbol |
| `resistor_symbol()` | :173 | US zigzag resistor symbol |
| `capacitor_symbol()` | :265 | Unpolarized capacitor symbol |
| `inductor_symbol()` | :357 | Arc coil inductor symbol |
| `stub_symbol()` | :419 | Minimal symbol (properties only, no graphics) |
| `spec_property_key()` | :462 | Generate property key from spec name |
| `symbol_for_part()` | :486 | Dispatch: pick template by part category/template field |

### mapping.py (30 lines)

Category-to-filename conventions.

| Export | Line | Description |
|---|---|---|
| `library_filename()` | :12 | Category --> `.kicad_sym` filename (e.g. `"00k-Resistors.kicad_sym"`) |
| `symbol_reference()` | :21 | Full KiCad symbol reference (e.g. `"00k-Resistors:RES-10K-1PCT-0603"`) |

### lib_table.py (116 lines)

sym-lib-table generation and merging.

| Export | Line | Description |
|---|---|---|
| `generate_sym_lib_table()` | :50 | Generate full sym-lib-table for kist libraries |
| `update_sym_lib_table()` | :82 | Merge kist entries into existing file, preserving non-kist entries |

### discovery.py (253 lines)

KiCad installation detection and variable resolution.

| Export | Line | Description |
|---|---|---|
| `LibTableEntry` | :28 | Dataclass: S-expression row from KiCad lib table |
| `KiCadEnvironment` | :37 | Dataclass: detected KiCad paths and variables |
| `detect_kicad()` | :160 | Detect KiCad installation, resolve paths |
| `resolve_uri()` | :192 | Resolve `${VAR}` references in URIs |
| `parse_lib_table()` | :218 | Parse fp-lib-table or sym-lib-table |

Internal: `_probe_versioned_dirs()`, `_nix_kicad_variables()`, `_build_variables()` handle Nix and standard KiCad installs.

### indexer.py (477 lines)

Build searchable index of KiCad footprints and symbols with clone support.

| Export | Line | Description |
|---|---|---|
| `LibraryItem` | :44 | Dataclass: single footprint or symbol from a library |
| `LibraryIndex` | :58 | Dataclass: combined index of footprints and symbols |
| `build_footprint_index()` | :68 | Index KiCad footprint libraries |
| `build_symbol_index()` | :116 | Index KiCad symbol libraries |
| `linked_footprint_for_symbol()` | :241 | Resolve symbol-to-footprint linkage |
| `clone_symbol_to_local_library()` | :274 | Clone symbol into local kist library |
| `clone_footprint_to_local_library()` | :331 | Clone footprint into local kist library |
| `load_or_build_index()` | :450 | Load from disk cache or build fresh (content-hash invalidation) |

### render.py (1,234 lines)

Render KiCad symbols and footprints to PIL Images for TUI previews.

| Export | Line | Description |
|---|---|---|
| `RenderTheme` | :31 | Dataclass: semantic colours for rendering |
| `DEFAULT_RENDER_THEME` | :45 | Default theme instance |
| `build_symbol_path_lookup()` | :51 | Map library names to .kicad_sym paths |
| `build_footprint_path_lookup()` | :74 | Map library names to .pretty dirs |
| `get_symbol_units()` | :462 | Extract unit numbers from multi-unit symbol |
| `render_symbol()` | :785 | Render symbol to PIL Image |
| `load_footprint()` | :988 | Load and cache .kicad_mod files |
| `render_footprint()` | :994 | Render footprint to PIL Image |

Handles arcs, beziers, polylines, fills, pins, text (with KiCad markup), pads, and layers. Uses PIL for rasterisation with configurable theme colours.

## Providers Module (`src/kist/providers/`)

### __init__.py (88 lines)

Provider detection and dispatch.

| Export | Line | Description |
|---|---|---|
| `detect_provider()` | :23 | Return (provider_name, identifier) from URL or MPN |
| `fetch_product()` | :51 | Detect provider, load creds/mapping, fetch product |

### models.py (59 lines)

| Export | Line | Description |
|---|---|---|
| `ProviderMappingConfig` | :8 | Mapping configuration for provider |
| `ProviderProduct` | :35 | Normalized product data from supplier API |

### digikey.py (397 lines)

DigiKey v4 API client.

| Export | Line | Description |
|---|---|---|
| `PARAMETER_MAP` | :32 | Raw DigiKey param names --> normalized targets |
| `CATEGORY_MAP` | :94 | DigiKey category names --> kist category codes |
| `MOUNTING_MAP` | :167 | Raw mounting strings --> canonical values |
| `default_mapping()` | :182 | Built-in DigiKey mapping defaults |
| `parse_digikey_url()` | :195 | Extract MPN from DigiKey URL |
| `DigiKeyClient` | :316 | v4 API client (OAuth2 client_credentials) |
| `.fetch_product()` | :357 | Fetch product details from DigiKey API |

## Error Hierarchy (`src/kist/errors.py`, 37 lines)

```
KistError
├── PartNotFoundError
├── DuplicatePartError
├── DatabaseError
├── LibraryNotFoundError
├── LibraryExistsError
├── ConfigError
├── ProviderError
│   └── DigiKeyError
```
