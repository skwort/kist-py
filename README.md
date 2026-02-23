# kist

**A lightweight component library manager for KiCad.**

kist manages your KiCad parts library from the terminal. It enforces consistent naming, pulls metadata from supplier APIs, generates KiCad symbols, and keeps everything in version-controllable files -- no servers, no databases, just your library and git.


> **Note:** kist is under active development. Expect breaking changes until a stable release.

## Why kist?

Managing a KiCad parts library by hand is tedious and error-prone. Existing tools either require heavyweight infrastructure (Inventree + Docker) or leave you editing files manually. kist sits in the middle -- structured enough to enforce conventions, light enough to stay out of your way.

- **Paste a DigiKey URL, get a part.** kist fetches metadata, classifies the part, generates a canonical name, and writes the KiCad symbol.
- **Three-tier part model.** Proprietary, semi-jellybean, and jellybean parts each get the right level of structure -- no more, no less.
- **Git-native.** Parts live in a JSON database, config in TOML. Readable diffs, easy merges, no lock-in.
- **KiCad integration.** Symbols are generated and synced automatically. One `.kicad_sym` per category, with a managed `sym-lib-table`.

## Features

- **TUI and CLI.** Browse, search, add, edit, and delete parts from an interactive terminal interface or via CLI commands.
- **Supplier integration.** Fetch part data from DigiKey by URL or MPN. More providers planned.
- **Canonical naming.** Parts are named automatically from their specifications (e.g. `RES-10K-1PCT-0603`). Names stay consistent across your library.
- **Symbol generation.** Resistor, capacitor, and inductor symbols are generated from templates. Other parts get a stub symbol with correct properties.
- **Library validation.** `kist check` catches name drift and duplicate parts.
- **Configurable categories.** Define your own categories with custom key specs, ref designators, and subcategories.
- **Settings UI.** Theme, DigiKey credentials, library config -- all editable from the TUI.

## Getting started

### Install

Requires Python 3.12+.

```bash
# With Nix flakes
nix profile install github:skwort/kist

# With uv
uv tool install kist

# With pipx
pipx install kist

# From source
git clone https://github.com/skwort/kist.git
cd kist
uv sync
```

### Create a library

```bash
kist init -p ~/my-kicad-lib
```

This opens the init wizard. Use `--no-tui` to skip it and create
the library with defaults.

### Link a KiCad project

```bash
cd ~/my-kicad-project
kist link ~/my-kicad-lib
```

This writes a `kist.toml` reference and creates a `lib/` symlink so KiCad can find your symbols via `${KIPRJMOD}/lib/`.

### Launch the TUI

```bash
kist
```

Running `kist` without a subcommand opens the interactive TUI. From there you can browse your library, search for parts, and add new ones.

### Add a part

From the TUI, press `Ctrl+N` to open the add screen. Paste a DigiKey URL or MPN into the input bar and press Enter -- kist fetches the metadata, populates the form, and lets you review before saving.

Or from the CLI:

```bash
kist add https://www.digikey.com/en/products/detail/...
```

### Other commands

```bash
kist search "10k"       # Search parts by name, description, tags, MPN
kist check              # Validate names and check for duplicates
kist sync               # Regenerate KiCad symbol files and lib tables
```

## How it works

kist manages a parts library stored in a `.kist/` directory:

```
my-library/
├── .kist/
│   └── config.toml      # Library configuration and categories
├── parts.json           # Part database (source of truth)
├── symbols/             # Generated .kicad_sym files (one per category)
├── footprints/
├── 3dmodels/
├── blocks/
└── sym-lib-table        # KiCad library table (auto-managed)
```

Parts are classified into three tiers:

| Tier | Example | Key fields |
|---|---|---|
| **Proprietary** | STM32F405 | MPN, manufacturer |
| **Semi-jellybean** | TL072 | MPN, manufacturer + alternates |
| **Jellybean** | 10K resistor | Specifications + alternates |

Each part gets a canonical name generated from its category, specifications, and package (e.g. `RES-10K-1PCT-0603`, `CAP-100n-50V-X7R-0402`). Names, values, and descriptions are derived from structured data -- not typed by hand.

When you save a part, kist writes to `parts.json`, generates or updates the appropriate `.kicad_sym` file, and refreshes the `sym-lib-table`. The KiCad files are always in sync with the database.

## Development

Requires [Nix](https://nixos.org/) with flakes enabled, or Python 3.12+ with uv.

```bash
direnv allow   # or: nix develop
uv sync --all-extras
```

### Checks

```bash
uv run pytest       # tests
ruff check          # lint
ruff format --check # format check
ty check            # type check
```

### Architecture

See [codemaps/](codemaps/) for a full module-level map of the codebase, and `docs/adr/` for architectural decision records.

## Acknowledgements

kist is built with [Textual](https://github.com/textualize/textual).

- [Posting](https://github.com/darrenburns/posting) -- A clean example of a domain-specific Textual app. Influenced the overall TUI layout and UX approach.
- [Toad](https://github.com/willmcgugan/toad) -- Its architecture was instructive when thinking about how to manage reactive state across screens.
- [Bagels](https://github.com/EnhancedJax/Bagels) -- Demonstrated how well a Textual TUI can work for data-entry workflows.
- [InvenTree](https://github.com/inventree/InvenTree) -- A full-featured inventory management system. kist exists for cases where InvenTree's infrastructure is more than you need.
- [Ki-nTree](https://github.com/sparkmicro/Ki-nTree) -- Bridges KiCad and InvenTree. Showed what a KiCad parts workflow could look like.
