# Codemap Index

> Freshness: 2026-02-23

kist -- KiCad parts library manager (v0.1.0, ~9,900 LOC source, ~7,700 LOC tests)

## Maps

- [architecture.md](architecture.md) -- System overview, data flow, mutation pipeline, dependencies
- [backend.md](backend.md) -- CLI commands, core modules, KiCad integration, providers, error hierarchy
- [frontend.md](frontend.md) -- TUI screens, widgets, modals, reactive state, form pipeline
- [data.md](data.md) -- Part models, config models, provider models, on-disk formats

## Summary

| Module | LOC | Files | Description |
|---|---|---|---|
| core/ | ~1,480 | 8 | Config, database, library, naming, categories, check, sync |
| tui/ | ~4,100 | 20 | Textual TUI (screens, widgets, modals, TCSS) |
| kicad/ | ~2,840 | 8 | Symbol libs, templates, rendering, discovery, indexer |
| sexpr.py | ~490 | 1 | S-expression parser/serializer |
| providers/ | ~540 | 3 | DigiKey API client, provider dispatch |
| models/ | ~210 | 3 | Part/config/provider Pydantic models |
| cli/ | ~210 | 2 | Typer CLI (init, link, add, search, check, sync) |
| errors.py | ~40 | 1 | Exception hierarchy |
| tests/ | ~7,700 | 35 | pytest suite |
