# Frontend (TUI)

> Freshness: 2026-02-15

## Overview

Textual-based terminal UI. ~2,440 LOC across 17 files.

## App (`src/kist/tui/app.py`, 202 lines)

| Export | Line | Description |
|---|---|---|
| `KistApp` | :26 | Main Textual app; manages library lifecycle and part mutations |
| `run_tui()` | :196 | Entry point for launching TUI from CLI |

**Reactive state:**
- `library_path` (:36) -- current library root
- `library_config` (:37) -- loaded LibraryConfig
- `project_dir` (:38) -- project directory (when linked to KiCad)
- `parts_version` (:39) -- incremented on mutations, triggers UI refresh

**Key methods:**
- `save_part(part, replacing=None)` (:82) -- persist part + sync pipeline
- `delete_part(ipn)` (:92) -- remove part + sync pipeline
- `update_library_config(config)` (:100) -- save config to disk
- `_after_mutation(db)` (:106) -- sync symbols, sym-lib-table, bump version
- `get_system_commands()` (:127) -- command palette entries (Add, Settings, Sync, Check, Manage categories)

## Screen Hierarchy

```
KistApp
├── BrowseScreen (default)
│   ├── KistHeader
│   ├── CategoryList (sidebar) + PartsTable (main) + search Input
│   └── Footer
├── AddScreen
│   ├── KistHeader
│   ├── URL/MPN Input bar
│   ├── PartForm (editable)
│   └── Footer
└── DetailModal
    └── PartForm (readonly, toggles to editable)
```

## Screens (`src/kist/tui/screens/`)

### browse.py (200 lines)

Main library overview with category sidebar and parts table.

| Export | Line | Description |
|---|---|---|
| `BrowseScreen` | :38 | Default screen |

**Layout:** CategoryList (left sidebar) | search Input + PartsTable (main panel)

**Bindings:** `q` quit, `/` focus search, `ctrl+n` add part

**Key methods:**
- `_on_library_changed()` (:77) -- loads DB, builds category counts
- `_apply_filters()` (:110) -- filters by category and search query
- `_on_parts_changed()` (:179) -- reloads on parts_version change

### detail.py (177 lines)

Modal for viewing/editing/deleting a part.

| Export | Line | Description |
|---|---|---|
| `DetailModal` | :18 | Part detail view with edit toggle |
| `ConfirmModal` | :155 | Generic yes/no confirmation dialog |

**Bindings:** `escape` close, `e` toggle edit, `d` delete, `ctrl+s` save

**Key methods:**
- `_load_part()` (:46) -- populate form, save snapshot for dirty check
- `action_save()` (:78) -- validate form, build Part, save via app
- `action_delete()` (:112) -- confirm then delete

### add.py (143 lines)

Full-screen form for adding a new part from URL/MPN or manual entry.

| Export | Line | Description |
|---|---|---|
| `AddScreen` | :23 | Add part screen |

**Bindings:** `escape` back, `ctrl+s` save

**Key methods:**
- `_start_fetch(url_or_mpn)` (:72) -- detect provider, start async worker
- `_fetch_worker()` (:87) -- fetch product data via providers module
- `action_save()` (:109) -- validate, build Part, save, clear form

## Widgets (`src/kist/tui/widgets/`)

### part_form.py (766 lines)

Largest file. Single-page composite form for all part tiers.

| Export | Line | Description |
|---|---|---|
| `PartForm` | :75 | 2x2 grid form (General + Suppliers / KiCad + Specs) |

**Modes:** `"editable"` (inputs) and `"readonly"` (static labels)

**Key methods:**
- `load_part(part)` (:535) -- populate from Part model
- `load_from_provider(product)` (:615) -- populate from ProviderProduct, auto-detect tier
- `clear()` (:666) -- reset all fields
- `to_dict()` (:708) -- extract form values for `build_part_from_form()`
- `_apply_tier_visibility(tier)` (:354) -- show/hide MPN, Manufacturer, Base PN fields

Inline sub-forms: specs DataTable + add row, suppliers DataTable + add row.

### category_list.py (45 lines)

| Export | Line | Description |
|---|---|---|
| `CategoryList` | :11 | OptionList sidebar with category counts |
| `.Selected` | :19 | Message posted on selection |

### parts_table.py (52 lines)

| Export | Line | Description |
|---|---|---|
| `PartsTable` | :19 | DataTable for part listing |

Columns: Name, Value, Package, Tier, Description. Row key = IPN.
Bindings: `j`/`k` navigate, `e` select.

### header.py (76 lines)

| Export | Line | Description |
|---|---|---|
| `KistHeader` | :56 | Title bar: page title (left), app title (center), library path (right) |
| `HeaderPageTitle` | :12 | Clickable icon + page title, opens command palette |
| `HeaderLibraryPath` | :28 | Watches app.library_path, displays relative path |

## Modals (`src/kist/tui/modals/`)

### categories.py (354 lines)

| Export | Line | Description |
|---|---|---|
| `CategoryFormModal` | :27 | Create/edit a single category (code, name, refdes, key specs, template, subcategories) |
| `CategoryManagerModal` | :236 | DataTable of all library categories with CRUD |

**CategoryFormModal bindings:** `escape` cancel, `ctrl+s` save
**CategoryManagerModal bindings:** `escape` close, `a` add, `e` edit, `d` delete

### check.py (49 lines)

| Export | Line | Description |
|---|---|---|
| `LibraryCheckModal` | :19 | Display library check results (name_drift, duplicate_identity) |

### settings.py (227 lines)

| Export | Line | Description |
|---|---|---|
| `SettingsModal` | :24 | User preferences and library config |

**Sections:** Appearance (theme), DigiKey API (client_id, client_secret), Library (prefix, separator, suppliers), Directories (symbols, footprints, 3dmodels).

Theme changes apply live with revert on cancel.

## Form Pipeline (`src/kist/tui/save.py`, 129 lines)

| Export | Line | Description |
|---|---|---|
| `ValidationNotice` | :17 | Exception for user-facing validation messages |
| `build_part_from_form()` | :21 | Dict + categories --> Part (generates name/value/description) |

## Themes (`src/kist/tui/themes.py`, 18 lines)

| Export | Line | Description |
|---|---|---|
| `NULL_THEME` | :5 | Dark theme (primary: #333333, error: #cc5555, success: #53ae71) |
