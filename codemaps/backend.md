# Backend

> Freshness: 2026-02-12

## CLI Module (`src/kist/cli/`)

### app.py (97 lines)

Typer application with callback + subcommands.

| Export | Line | Description |
|---|---|---|
| `app` | :9 | Typer instance, `invoke_without_command=True` |
| `main()` | :17 | Callback: `--version` flag, TUI stub |
| `init()` | :33 | Create library: delegates to `core.library.init_library` |
| `link()` | :69 | Link project to library: delegates to `core.library.link_library` |
| `add()` | :88 | Stub -- not yet implemented |
| `search()` | :94 | Stub -- not yet implemented |

Imports are deferred inside command bodies to keep CLI startup fast.

## Core Module (`src/kist/core/`)

### config.py (85 lines)

Configuration I/O using tomlkit for round-trip TOML.

| Export | Line | Description |
|---|---|---|
| `KIST_MARKER` | :15 | `".kist"` directory name |
| `PROJECT_REF` | :16 | `"kist.toml"` filename |
| `LIBRARY_CONFIG` | :17 | `"config.toml"` filename |
| `load_global_config()` | :28 | Read global config, defaults if absent |
| `resolve_init_config()` | :40 | Merge defaults + global + CLI overrides |
| `load_library_config()` | :50 | Read `.kist/config.toml` |
| `save_library_config()` | :62 | Write `.kist/config.toml` |
| `load_project_ref()` | :71 | Read `kist.toml` project ref |
| `save_project_ref()` | :82 | Write `kist.toml` project ref |

Config dir: `KIST_CONFIG_DIR` env var, or `platformdirs.user_config_dir("kist")`.

### database.py (144 lines)

JSON-backed parts database with CRUD operations.

| Export | Line | Description |
|---|---|---|
| `create_empty()` | :20 | Write empty `parts.json` |
| `PartsDatabase` | :26 | Main CRUD class |
| `.load()` | :50 | Deserialize from JSON |
| `.save()` | :64 | Serialize to JSON (sorted by name) |
| `.add()` | :84 | Add part, auto-generate UUID IPN |
| `.remove()` | :99 | Remove by IPN |
| `.get()` | :107 | Lookup by IPN |
| `.resolve()` | :111 | Name -> IPN lookup |
| `.list_parts()` | :115 | All parts sorted by name |
| `.search()` | :119 | Substring search across fields |

Uses `pydantic.TypeAdapter` for the `Part` discriminated union (type alias, not BaseModel).

### library.py (145 lines)

Library lifecycle: create, link, discover.

| Export | Line | Description |
|---|---|---|
| `init_library()` | :23 | Create `.kist/`, `config.toml`, `parts.json`, asset dirs |
| `link_library()` | :65 | Create `kist.toml` + `lib/` symlink/junction |
| `find_library()` | :114 | Walk-up discovery from start dir to filesystem root |

`_create_lib_link()` (:89) handles symlink (Unix) vs junction (Windows).

### naming.py (648 lines)

Engineering value normalisation, canonical name generation, and part identity.

**Normalisers** (all `str -> str`):

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
| `generate_name()` | :481 | Canonical part name from structured fields (ADR-001 §2) |
| `generate_value()` | :525 | Schematic display value (ADR-001 §8) |
| `generate_description()` | :585 | Human-readable description |
| `get_identity()` | :624 | Deduplication tuple (ADR-001 §7) |

**Key data structures**:

| Constant | Line | Description |
|---|---|---|
| `KEY_SPECS` | :379 | `(Category, subcategory) -> [spec field names]` |
| `SPEC_NORMALISERS` | :403 | `spec_field_name -> normaliser function` |
| `_SI_PREFIXES` | :19 | SI prefix letter -> multiplier |
| `_PACKAGE_ALIASES` | :53 | Common package name aliases |

Internal: `_parse_engineering()` (:99) parses any engineering value string (SI prefixes, shorthand like `4K7`). `_format_eng_rlc()` (:144) formats float back to shorthand.

## Error Hierarchy (`src/kist/errors.py`, 29 lines)

```
KistError
├── PartNotFoundError
├── DuplicatePartError
├── DatabaseError
├── LibraryNotFoundError
├── LibraryExistsError
└── ConfigError
```
