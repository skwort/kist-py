# Codemap Index

> Freshness: 2026-02-15

kist -- KiCad parts library manager (v0.1.0, ~6,100 LOC source, ~5,800 LOC tests)

## Maps

- [codemaps/architecture.md](codemaps/architecture.md) -- System overview, data flow, mutation pipeline, dependencies
- [codemaps/backend.md](codemaps/backend.md) -- CLI commands, core modules, KiCad integration, providers, error hierarchy
- [codemaps/frontend.md](codemaps/frontend.md) -- TUI screens, widgets, modals, reactive state, form pipeline
- [codemaps/data.md](codemaps/data.md) -- Part models, config models, provider models, on-disk formats

## Summary

| Module | LOC | Files | Description |
|---|---|---|---|
| core/ | ~1,200 | 7 | Config, database, library, naming, categories, check, sync |
| tui/ | ~2,440 | 17 | Textual TUI (screens, widgets, modals) |
| kicad/ | ~770 | 5 | Symbol libraries, templates, lib-table, mapping |
| sexpr.py | ~490 | 1 | S-expression parser/serializer |
| providers/ | ~540 | 3 | DigiKey API client, provider dispatch |
| models/ | ~210 | 3 | Part/config/provider Pydantic models |
| cli/ | ~200 | 1 | Typer CLI (init, link, add, search, check, sync) |
| errors.py | ~40 | 1 | Exception hierarchy |
| tests/ | ~5,800 | 35 | pytest suite |
