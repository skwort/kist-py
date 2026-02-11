# ADR-003: Library Structure & Discovery

**Status**: Draft
**Date**: 2026-02-11

## Context

ADR-001 defines the data model and ADR-002 defines KiCad integration.
Before implementing commands that operate on libraries, we need to
answer three questions:

1. How does a kist library lay out on disk?
2. How is kist configured (per-user, per-library, per-project)?
3. How does kist find the library it should operate on?

These decisions affect every subsequent command.

### Requirements

- A library must be self-contained -- cloning the repository gives you
  everything needed to use it.
- Configuration must support user-level defaults that individual
  libraries can override.
- KiCad projects must be able to reference a library that lives outside
  the project directory (via Git submodule or symlink).
- `kist init` must be safe to run in an existing directory (e.g. a
  repo that already has `symbols/` and `footprints/`).

## Decision

### 1. Library Directory Structure

A kist library is a directory with the following default layout:

```
my-library/
├── parts.json              # Part database (ADR-001)
├── symbols/                # KiCad .kicad_sym files (ADR-002)
├── footprints/             # KiCad .kicad_mod files in .pretty dirs
├── 3dmodels/               # STEP/WRL 3D models
├── blocks/                 # Design block libraries (KiCad 9+, ADR-002 §5)
└── .kist/
    └── config.toml         # Library-level configuration
```

The `.kist/` directory is the marker that identifies a directory as a
kist library. Its presence is how discovery works (see §3).

All directory names (`symbols`, `footprints`, `3dmodels`, `blocks`)
are configurable via `.kist/config.toml`. The defaults match the
names used in ADR-002.

### 2. Configuration Hierarchy

Configuration exists at three levels. Lower levels override higher.
All config files use TOML -- `tomlkit` for both reading and writing
(preserves comments and formatting on round-trip).

#### Global Config (`~/.config/kist/config.toml`)

User-level defaults. The config directory is resolved as:

1. `KIST_CONFIG_DIR` environment variable (if set)
2. `platformdirs.user_config_dir("kist")` (platform default)

The env var exists for testability (test fixtures use `monkeypatch` to
point at a temp directory) and for users with non-standard config
layouts (dotfiles managers, NixOS, etc.).

Contains preferences that apply across all libraries.

Fields:

| Field             | Type            | Default          | Description                          |
|-------------------|-----------------|------------------|--------------------------------------|
| `symbols_dir`     | `str`           | `"symbols"`      | Default symbol library directory     |
| `footprints_dir`  | `str`           | `"footprints"`   | Default footprint library directory  |
| `models_dir`      | `str`           | `"3dmodels"`     | Default 3D model directory           |
| `blocks_dir`      | `str`           | `"blocks"`       | Default design blocks directory      |
| `suppliers`       | `list[str]`     | *(see below)*    | Known supplier names for validation  |

Default suppliers: `["digikey", "mouser", "lcsc", "farnell", "newark",
"rs", "tme"]`.

The global config file is **not** auto-created. It only exists if the
user explicitly creates it or runs a future `kist config --global`
command. When absent, built-in defaults apply.

#### Library Config (`.kist/config.toml`)

Per-library settings. Created by `kist init`. The library config
always contains concrete values -- all fields are resolved at init
time from global defaults (or CLI overrides) and written into the
library config. This makes the library config fully self-contained:
any kist command can read it and know exactly where things are and
which suppliers are valid, without reimplementing the global config
merge at runtime.

Fields:

| Field             | Type            | Required | Description                           |
|-------------------|-----------------|----------|---------------------------------------|
| `version`         | `int`           | yes      | Config format version (currently `1`) |
| `symbols_dir`     | `str`           | yes      | Symbol library directory              |
| `footprints_dir`  | `str`           | yes      | Footprint library directory           |
| `models_dir`      | `str`           | yes      | 3D model directory                    |
| `blocks_dir`      | `str`           | yes      | Design blocks directory               |
| `suppliers`       | `list[str]`     | yes      | Known supplier names for validation   |

Example `.kist/config.toml`:

```toml
version = 1
symbols_dir = "symbols"
footprints_dir = "footprints"
models_dir = "3dmodels"
blocks_dir = "blocks"
suppliers = ["digikey", "mouser", "lcsc", "farnell", "newark", "rs", "tme"]
```

All fields are always present because they are resolved at
`kist init` time. Global config only matters at init time -- it
provides defaults that get baked into the library config.

#### Project Reference (`kist.toml`)

A project-level file that points to a library. Placed at the root of
a KiCad project (or any working directory) to tell kist where the
library lives. Analogous to `pyproject.toml` -- a well-known name at
the project root.

Fields:

| Field           | Type   | Required | Description                                |
|-----------------|--------|----------|--------------------------------------------|
| `version`       | `int`  | yes      | Config format version (currently `1`)      |
| `library_path`  | `str`  | yes      | Path to library root, relative to this file|

The `kist.toml` project reference contains only the library path. It
is intentionally minimal -- project-specific settings belong in the
library's own config. A project reference simply answers "where is the
library?"

Example:

```toml
version = 1
library_path = "./lib"
```

#### Config Resolution

Resolution at init time: built-in defaults -> global config -> CLI
flags. The result is written into `.kist/config.toml`. All fields --
directory names and suppliers -- are resolved and stored.

Resolution at runtime: read `.kist/config.toml` directly. The config
is self-contained; no fallback to global config is needed.

### 3. Library Discovery

When a kist command needs to find the library, it walks up from the
current working directory checking each level:

At each directory, check for `.kist/`. If found, that directory is the
library root -- you are inside the library itself. If not, check for
`kist.toml`. If found, read the `library_path`, resolve it relative
to the file's parent directory, and verify that path contains `.kist/`.

If neither marker is found, move to the parent directory and repeat.

Discovery walks up to the filesystem root (`/` on Unix, drive root on
Windows). If the root is reached without finding either marker, error
with a helpful message:

```
Not a kist library (or any parent up to /).
Run 'kist init' to create a new library, or
'kist link <path>' to link to an existing one.
```

Checking `.kist/` before `kist.toml` at each level means that if
both exist in the same directory, the library marker takes priority.

Discovery uses the logical working directory path (does not resolve
symlinks in the walk-up path itself). At each level, `.kist/` and
`kist.toml` are checked using normal path operations, which follow
symlinks transparently -- a symlinked library directory is found
correctly.

### 4. `kist init`

```bash
kist init [--path <dir>] [--symbols-dir <name>] [--footprints-dir <name>] [--models-dir <name>] [--blocks-dir <name>]
```

Creates a new kist library at the target directory (default: cwd).

Actions:
1. Resolve all config fields: CLI flags -> global config -> built-in
   defaults.
2. Create `.kist/config.toml` with the resolved values.
3. Create `parts.json` with empty database
   (`{"version": 1, "parts": {}}`).
4. Create the configured subdirectories (`symbols/`, `footprints/`,
   `3dmodels/`, `blocks/`) if they do not already exist.

Safe for existing directories: never overwrites existing files, never
deletes existing directories. If `.kist/` already exists, the command
fails with a clear error ("already initialised").

### 5. `kist link`

```bash
kist link <library> [--path <dir>]
```

Connects a project directory to an existing kist library. Creates a
`kist.toml` project reference and, when needed, a filesystem symlink
for KiCad path resolution.

The target directory (default: cwd) is where `kist.toml` is written.
`<library>` is the path to the library root (must contain `.kist/`).

Actions:
1. Resolve `<library>` and verify it contains `.kist/`.
2. Compute the relative path from the target directory to the library.
3. Write `kist.toml` with the relative path.
4. If `lib/` does not already exist in the target directory, create a
   symlink `lib -> <relative-library-path>` (for KiCad's
   `${KIPRJMOD}/lib/` convention). If `lib/` already exists (e.g. the
   library is a Git submodule at that path), skip the symlink.

Fails if `kist.toml` already exists in the target directory, or if
`<library>` does not contain a valid library.

#### Examples

Single-board project with submodule:

```bash
cd my-project
git submodule add <url> lib
kist link ./lib
# writes kist.toml, lib/ already exists -> no symlink
```

Multi-board project from the root:

```bash
kist init --path lib
kist link lib --path board-a
# writes board-a/kist.toml (library_path = "../lib")
# creates board-a/lib -> ../lib symlink
kist link lib --path board-b
# same for board-b
```

After linking, kist commands work from any linked directory and
KiCad resolves `${KIPRJMOD}/lib/...` paths correctly.

### 6. Implementation

#### Models

```python
# src/kist/models/config.py

class LibraryConfig(BaseModel):
    """Always has concrete values -- resolved at init time."""
    version: int = 1
    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = DEFAULT_SUPPLIERS

class GlobalConfig(BaseModel):
    """User-level defaults. All fields optional with built-in defaults."""
    symbols_dir: str = "symbols"
    footprints_dir: str = "footprints"
    models_dir: str = "3dmodels"
    blocks_dir: str = "blocks"
    suppliers: list[str] = DEFAULT_SUPPLIERS

class ProjectRef(BaseModel):
    version: int = 1
    library_path: str
```

#### Config Resolution

```python
# src/kist/core/config.py

def load_global_config() -> GlobalConfig: ...
def resolve_init_config(**overrides) -> LibraryConfig: ...
def load_library_config(library_root: Path) -> LibraryConfig: ...
```

`resolve_init_config` merges built-in defaults, global config, and
CLI overrides to produce a `LibraryConfig` for writing. It is called
at `kist init` time only. `load_library_config` reads
`.kist/config.toml` at runtime -- no merging needed.

#### Library Operations

```python
# src/kist/core/library.py

def init_library(path: Path, **overrides) -> Path: ...
def link_library(target: Path, library: Path) -> Path: ...
def find_library(start: Path | None = None) -> Path: ...
```

#### Errors

New error types for library and config operations:

```python
# Added to src/kist/errors.py

class LibraryNotFoundError(KistError): ...
class LibraryExistsError(KistError): ...
class ConfigError(KistError): ...
```

`LibraryNotFoundError` -- discovery exhausted without finding a
library. `LibraryExistsError` -- `kist init` in an already-initialised
directory. `ConfigError` -- corrupt, missing, or invalid config files
(covers both `.kist/config.toml` and `kist.toml`).

## Consequences

### Positive

- **Simple discovery**: Walk-up-to-root is the standard pattern used
  by Git, npm, Cargo, and other tools. Users understand it
  intuitively.
- **Non-destructive init**: Safe to run in an existing directory.
  No data loss risk.
- **Self-contained library config**: All fields are resolved once at
  init and stored. Runtime reads `.kist/config.toml` and has
  everything it needs -- no config merging, no fallback chains.
- **Flexible layout**: Directory names are configurable, but sane
  defaults mean most users never touch config.
- **Submodule-friendly**: `kist.toml` decouples project location
  from library location, supporting Git submodule workflows.
- **No magic**: The `.kist/` marker is explicit and discoverable.
  Users can see and understand the library structure.
- **TOML is human-friendly**: Easy to read and edit by hand, which
  is the whole point of a config file. `tomlkit` for reading and
  writing preserves comments and formatting on round-trip.

### Negative

- **Two discovery markers**: `.kist/` and `kist.toml` are different
  things with different semantics. Users must understand the
  distinction. Clear error messages and documentation mitigate this.
- **No auto-created global config**: Users who want global defaults
  must manually create the file. This is intentional -- most users
  will never need global config, and auto-creating dotfiles is
  annoying.

### Neutral

- **No nested libraries**: A directory cannot be both a library and
  inside another library. Discovery stops at the first `.kist/`
  marker. This matches the mental model (one library per repo).
- **Project ref is minimal**: `kist.toml` only has a `library_path`
  and `version`. If project-specific settings are needed later, the
  model can grow without breaking existing files (new optional
  fields).
