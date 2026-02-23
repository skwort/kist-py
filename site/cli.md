# CLI Reference

## Usage

```
kist [OPTIONS] COMMAND [ARGS]
```

Running `kist` without a subcommand launches the interactive TUI.

## Commands

### `kist init`

Initialize a new kist parts library.

```bash
kist init [PATH]
```

Creates a `.kist/` directory with `config.toml`, `parts.json`, and asset directories (symbols, footprints, 3dmodels). Defaults to the current directory if no path is given.

### `kist link`

Link a KiCad project directory to an existing kist library.

```bash
kist link LIBRARY_PATH
```

Creates a `kist.toml` project reference and a `lib/` symlink for KiCad's `${KIPRJMOD}/lib/` convention.

### `kist add`

Add a part to the library.

```bash
kist add [URL_OR_MPN]
```

If a DigiKey URL or MPN is provided, kist fetches metadata from the supplier API and populates the part form. Opens the TUI add screen for review and editing.

### `kist search`

Search for parts in the library.

```bash
kist search QUERY
```

Searches across part name, description, tags, and MPN. Results are displayed as a table.

### `kist check`

Validate the parts library.

```bash
kist check
```

Checks for:

- **Name drift** -- parts whose stored name doesn't match what would be generated from their current data.
- **Duplicate identity** -- multiple parts with the same identity tuple (category + key specs + package).

### `kist sync`

Synchronize KiCad files with the parts database.

```bash
kist sync
```

Regenerates all `.kicad_sym` symbol files and updates the `sym-lib-table` in the linked project directory. This is run automatically after part mutations in the TUI, but can be invoked manually if needed.

## Global options

### `--version`

Show the kist version and exit.

### `--help`

Show help for any command.

```bash
kist --help
kist init --help
```
