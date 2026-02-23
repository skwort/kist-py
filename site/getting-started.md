# Getting Started

## Install

Requires Python 3.12+.

```bash
# With Nix flakes
nix profile install github:skwort/kist

# With uv
uv tool install kist

# With pipx
pipx install kist
```

Or from source:

```bash
git clone https://github.com/skwort/kist.git
cd kist
uv sync
```

## Create a library

```bash
kist init ~/my-kicad-lib
```

This creates a `.kist/` directory with `config.toml`, `parts.json`, and asset directories for symbols, footprints, and 3D models.

## Link a KiCad project

```bash
cd ~/my-kicad-project
kist link ~/my-kicad-lib
```

This writes a `kist.toml` reference and creates a `lib/` symlink so KiCad can find your symbols via `${KIPRJMOD}/lib/`.

## Launch the TUI

```bash
kist
```

Running `kist` without a subcommand opens the interactive TUI. From there you can browse your library, search for parts, and add new ones.

## Add a part

From the TUI, press ++ctrl+n++ to open the add screen. Paste a DigiKey URL or MPN into the input bar and press ++enter++ -- kist fetches the metadata, populates the form, and lets you review before saving.

Or from the CLI:

```bash
kist add https://www.digikey.com/en/products/detail/...
```

## Next steps

- Read [Concepts](concepts.md) to understand the three-tier part model and library structure.
- See [CLI Reference](cli.md) for all available commands.
