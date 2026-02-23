# Architecture

> Freshness: 2026-02-23

## Overview

kist is a KiCad parts library manager. Project dir is `kip`, Python package is `kist`.

```
src/kist/
├── __init__.py          # version
├── __main__.py          # entrypoint --> cli.app:app
├── errors.py            # exception hierarchy
├── sexpr.py             # S-expression parser/serializer (KiCad file format)
├── cli/
│   └── app.py           # Typer CLI (init, link, add, search, check, sync)
├── core/
│   ├── categories.py    # built-in category definitions
│   ├── check.py         # library validation (name drift, duplicate identity)
│   ├── config.py        # TOML config I/O, resolution, provider mapping
│   ├── database.py      # JSON-backed PartsDatabase CRUD
│   ├── library.py       # init, link, discovery logic
│   ├── naming.py        # value normalisation, name/value/description gen
│   └── sync.py          # push part metadata to .kicad_sym + sym-lib-table
├── kicad/
│   ├── discovery.py     # KiCad installation detection, variable resolution
│   ├── indexer.py       # library indexing, clone operations, caching
│   ├── lib_table.py     # sym-lib-table generation/merging
│   ├── mapping.py       # category --> filename/symbol-reference mapping
│   ├── render.py        # symbol/footprint rendering to PIL Images
│   ├── symbols.py       # SymbolLibrary: .kicad_sym file abstraction
│   └── templates.py     # symbol tree builders (resistor, capacitor, inductor, stub)
├── models/
│   ├── __init__.py      # re-exports all public types
│   ├── config.py        # LibraryConfig, GlobalConfig, ProjectRef, CategoryDef
│   └── part.py          # Part union, PartBase, enums
├── providers/
│   ├── __init__.py      # detect_provider(), fetch_product() dispatch
│   ├── digikey.py       # DigiKey v4 API client + parameter/category mapping
│   └── models.py        # ProviderProduct, ProviderMappingConfig
└── tui/
    ├── app.py           # KistApp (Textual), mutation pipeline, command palette
    ├── kist.tcss        # Textual CSS (623 lines)
    ├── themes.py        # custom themes + Textual-to-render theme conversion
    ├── save.py          # form --> Part builder with validation
    ├── screens/
    │   ├── browse.py    # main screen: category sidebar + parts table + search
    │   ├── detail.py    # modal: view/edit/delete a part
    │   ├── add.py       # full screen: add part from URL/MPN or manual entry
    │   └── init.py      # full screen: library creation wizard
    ├── widgets/
    │   ├── category_list.py  # category sidebar (OptionList)
    │   ├── header.py         # header bar (title + library path)
    │   ├── part_form.py      # single-page part editor (929 LOC, largest widget)
    │   └── parts_table.py    # DataTable for parts listing
    └── modals/
        ├── categories.py     # category create/edit + manager modals
        ├── check.py          # library validation results
        ├── library_search.py # fzf-style search with live symbol/footprint preview
        └── settings.py       # theme, DigiKey creds, library config
```

~9,900 LOC source, ~7,700 LOC tests (46 source files, 35 test files).

## Data Flow

```
User
  │
  ├── CLI ──────────────────────────────────────────────────────────────┐
  │                                                                     │
  └── TUI (Textual) ──► tui/app.py ──► tui/save.py ──► core/naming.py  │
         │                   │                                          │
         │                   ├── core/database.py ──► models/part.py    │
         │                   │         │                                │
         │                   │         ▼                                │
         │                   │    parts.json (on disk)                  │
         │                   │                                          │
         │                   ├── core/sync.py ──► kicad/symbols.py ─────┤
         │                   │        │           kicad/templates.py    │
         │                   │        └────────── kicad/lib_table.py    │
         │                   │                                          │
         │                   └── core/config.py ──► models/config.py    │
         │                            │                                 │
         │                            ▼                                 │
         │                      tomlkit (TOML I/O)                      │
         │                                                              │
         ├── tui/screens/add.py ──► providers/ ──► DigiKey v4 API       │
         │                                                              │
         └── tui/modals/library_search.py                               │
                  │                                                     │
                  ├── kicad/discovery.py ──► detect KiCad installation   │
                  ├── kicad/indexer.py ──► build symbol/footprint index  │
                  └── kicad/render.py ──► PIL preview images            │
                                                                        │
cli/app.py ◄────────────────────────────────────────────────────────────┘
     │
     ├── core/library.py  (init, link, discover)
     ├── core/check.py    (validate names, find duplicates)
     └── core/sync.py     (push to KiCad files)
```

### Mutation Pipeline (TUI)

```
save_part() / delete_part()
  --> PartsDatabase.add/remove()
  --> sync_symbols()        # write .kicad_sym per category
  --> sync_sym_lib_table()  # update sym-lib-table in project dir
  --> parts_version++       # reactive: triggers BrowseScreen reload
```

### Library Search Pipeline

```
LibrarySearchModal
  --> kicad/discovery.detect_kicad()     # find KiCad installation
  --> kicad/indexer.load_or_build_index() # cached symbol/footprint index
  --> kicad/render.render_symbol()        # live preview on highlight
  --> kicad/indexer.clone_symbol_to_local_library()  # on confirm
```

## Key Decisions

- **ADR-001**: Three-tier part model (proprietary / semi-jellybean / jellybean) as Pydantic discriminated union on `tier` field; canonical naming via key specs (ADR-001 §2,§7,§8)
- **ADR-002**: KiCad integration -- S-expression parser (`sexpr.py`), symbol templates, per-category `.kicad_sym` files, `sym-lib-table` merging
- **ADR-003**: Library structure -- `kist init` creates library, `kist link` connects project; walk-up discovery; `lib/` symlink for KiCad
- Config resolved at init time -- library config is self-contained
- `version = 1` in all config files for forward compatibility
- JSON database with immediate save-on-mutate
- DigiKey v4 API via OAuth2 client_credentials grant
- KiCad symbol templates dispatch on category + template field
- User-defined categories stored in library config, merged with built-in defaults
- Library index cached to disk with content-hash invalidation

## Dependencies

| Dependency | Purpose |
|---|---|
| typer | CLI framework |
| rich | Terminal formatting (CLI tables, progress) |
| pydantic | Data validation and models |
| httpx | HTTP client (DigiKey API) |
| platformdirs | OS-appropriate config dirs |
| tomlkit | Round-trip TOML read/write |
| textual | TUI framework (screens, widgets, reactive state) |
| pillow | Symbol/footprint rendering for TUI previews |

## Entry Points

- `kist` script --> `kist.cli.app:app` (pyproject.toml `[project.scripts]`)
- `python -m kist` --> `__main__.py` --> same
- No-subcommand invocation launches TUI via `tui.app.run_tui()`
