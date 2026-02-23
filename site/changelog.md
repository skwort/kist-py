# Changelog

## 0.1.0 (unreleased)

Initial release.

### Core

- Three-tier part model (proprietary, semi-jellybean, jellybean)
- CLI commands: `init`, `link`, `add`, `search`, `check`, `sync`
- Canonical naming -- proprietary and semi-jellybean parts use MPN
  only; jellybean parts include package
- Configurable categories with custom key specs and subcategories
- Library validation (name drift, duplicate identity detection)
- DigiKey v4 API integration with RoHS and REACH status extraction

### TUI

- Interactive browse, add, and detail screens
- Interactive init wizard for library creation (`kist init`)
- Settings modal (theme, DigiKey credentials, library config)
- Fuzzy library search modal for symbols and footprints from installed
  KiCad libraries
- Symbol and footprint preview rendering with theme-aware colours
- Clone symbols and footprints from KiCad libraries into the local
  library
- Auto-fill footprint from selected symbol
- Editable part name field

### KiCad

- Symbol generation (resistor, capacitor, inductor, stub templates)
- Per-category `.kicad_sym` files with `sym-lib-table` management
- Part specs pushed as symbol properties
- KiCad installation discovery (including Nix-managed installs)
- Library index builder for symbols and footprints
- KiCad text markup rendering for preview
