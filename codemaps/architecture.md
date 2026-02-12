# Architecture

> Freshness: 2026-02-12

## Overview

kist is a KiCad parts library manager. Project dir is `kip`, Python package is `kist`.

```
src/kist/
├── __init__.py          # version
├── __main__.py          # entrypoint -> cli.app:app
├── errors.py            # exception hierarchy
├── cli/
│   └── app.py           # Typer CLI (init, link, add*, search*)
├── core/
│   ├── config.py        # TOML config I/O, resolution
│   ├── database.py      # JSON-backed PartsDatabase CRUD
│   ├── library.py       # init, link, discovery logic
│   └── naming.py        # value normalisation, name/value/description gen
└── models/
    ├── __init__.py       # re-exports all public types
    ├── config.py         # LibraryConfig, GlobalConfig, ProjectRef
    └── part.py           # Part union, PartBase, enums
```

~1390 LOC source, ~1600 LOC tests (14 source files, 11 test files).

## Data Flow

```
User CLI
  │
  ▼
cli/app.py  ──► core/library.py  ──► core/config.py  ──► models/config.py
                     │                     │
                     │                     ▼
                     │               tomlkit (TOML I/O)
                     ▼
               core/database.py  ──► models/part.py
                     │                    ▲
                     ▼                    │
               parts.json          core/naming.py
              (on disk)         (normalisation, name gen,
                                 value gen, identity)
```

## Key Decisions

- **ADR-001**: Three-tier part model (proprietary / semi-jellybean / jellybean) as Pydantic discriminated union on `tier` field; canonical naming via key specs (ADR-001 §2,§7,§8)
- **ADR-002**: KiCad integration approach (not yet implemented)
- **ADR-003**: Library structure -- `kist init` creates library, `kist link` connects project; walk-up discovery; `lib/` symlink for KiCad
- Config resolved at init time -- library config is self-contained
- `version = 1` in all config files for forward compatibility
- JSON database with immediate save-on-mutate

## Dependencies

| Dependency | Purpose |
|---|---|
| typer | CLI framework |
| rich | Terminal formatting |
| pydantic | Data validation and models |
| pydantic-settings | *unused -- should be removed* |
| httpx | HTTP client (supplier APIs, future) |
| structlog | Structured logging (future) |
| platformdirs | OS-appropriate config dirs |
| tomlkit | Round-trip TOML read/write |

## Entry Points

- `kist` script -> `kist.cli.app:app` (pyproject.toml `[project.scripts]`)
- `python -m kist` -> `__main__.py` -> same
