# CLI Reference

## Usage

```
kist [OPTIONS] COMMAND [ARGS]
```

Running `kist` without a subcommand launches the interactive TUI.

## Global options

| Option | Description |
|---|---|
| `--version`, `-v` | Show version and exit. |
| `--help` | Show help for any command. |

## Commands

### `kist init`

Initialise a new kist parts library.

```bash
kist init [OPTIONS]
```

By default, opens the interactive init wizard. Use `--no-tui` to skip the
wizard and create the library with defaults.

| Option | Default | Description |
|---|---|---|
| `--path`, `-p` | `.` | Directory to initialise. |
| `--symbols-dir` | `symbols` | Symbol library directory name. |
| `--footprints-dir` | `footprints` | Footprint library directory name. |
| `--models-dir` | `3dmodels` | 3D model directory name. |
| `--blocks-dir` | `blocks` | Design blocks directory name. |
| `--no-tui` | | Skip interactive wizard, use CLI defaults. |

### `kist link`

Link a project directory to an existing kist library.

```bash
kist link LIBRARY_PATH [OPTIONS]
```

Creates a `kist.toml` project reference and a `lib/` symlink so KiCad can
find your symbols via `${KIPRJMOD}/lib/`.

| Argument / Option | Default | Description |
|---|---|---|
| `LIBRARY_PATH` | *(required)* | Path to an existing kist library. |
| `--path`, `-p` | `.` | Project directory to link from. |

### `kist add`

Add a part to the library.

```bash
kist add [URL_OR_MPN]
```

If a DigiKey URL or MPN is provided, kist fetches metadata from the
supplier API and populates the part form. Opens the TUI add screen for
review and editing.

| Argument | Description |
|---|---|
| `URL_OR_MPN` | *(optional)* DigiKey URL or manufacturer part number to fetch. |

### `kist search`

Search for parts in the library.

```bash
kist search QUERY
```

Searches across part name, description, tags, MPN, and base part
number. Results are displayed as a table with name, tier, category,
and description columns.

| Argument | Description |
|---|---|
| `QUERY` | *(required)* Search term. |

### `kist check`

Validate the parts library.

```bash
kist check
```

Checks for:

- **Name drift** -- parts whose stored name doesn't match what would be
  generated from their current data.
- **Duplicate identity** -- multiple parts with the same identity tuple
  (category + key specs + package).

Exits with code 1 if any issues are found.

### `kist sync`

Sync KiCad symbol files and lib tables with the parts database.

```bash
kist sync
```

Regenerates all `.kicad_sym` symbol files and updates the `sym-lib-table`
in the linked project directory. This is run automatically after part
mutations in the TUI, but can be invoked manually if needed.

If no project directory is found (i.e. no `kist.toml` above the library),
the `sym-lib-table` update is skipped.
