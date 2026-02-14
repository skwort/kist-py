# ADR-005: TUI State Management

**Status**: Draft
**Date**: 2026-02-14

## Context

The TUI has grown to include browse, add, edit/delete, settings, and
category management screens. As screens were added, a problematic
pattern emerged: screens reach into the app instance to get
`library_path`, then independently load config and create database
instances to perform I/O.

```python
# This pattern appears 6+ times across screens/modals
app: KistApp = self.app  # type: ignore[assignment]
library_path = app.library_path
config = load_library_config(library_path)
db = PartsDatabase(library_path / "parts.json")
db.load()
db.add(part)
```

### Problems

1. **Tight coupling** -- screens depend on the concrete `KistApp` class
   and require a `# type: ignore` cast to access `library_path`.

2. **Scattered I/O** -- database and config operations are duplicated
   across AddScreen, DetailModal, BrowseScreen, SettingsModal, and
   CategoryManagerModal. Each screen independently loads config and
   creates database instances.

3. **No single owner** -- there is no clear boundary between
   "presentation" and "persistence". Screens handle form validation,
   part construction, database saving, and user notification all in
   one method.

4. **Config reloaded unnecessarily** -- library config is loaded from
   disk on every save/edit/delete operation, even though it rarely
   changes during a session. When it does change (settings modal),
   the app should know about it.

### Upcoming requirements

Two planned features make this refactor urgent rather than optional:

- **Sync on save** -- every part mutation must regenerate
  `.kicad_sym` files. This logic already exists in
  `core.sync.sync_symbols()` and must not be duplicated across
  screens.
- **Git integration** -- part add/edit/delete should auto-commit.
  This requires a single point where all mutations flow through,
  so the commit message can describe the operation.

Together these mean every part mutation triggers a pipeline (DB
write, symbol sync, git commit, UI refresh) that must be owned by
one component. If screens perform their own I/O, each screen would
need to duplicate this pipeline.

### Current state usage

Every screen that does I/O follows the same three steps:

1. Get `library_path` from app
2. `load_library_config(library_path)` to get config
3. `PartsDatabase(library_path / "parts.json").load()` to get database

What screens actually need from this:

- **AddScreen / DetailModal**: `config.categories` and
  `config.separator` for `build_part_from_form()`, plus a way to
  persist the result.
- **BrowseScreen**: the list of parts (already uses a reactive watcher
  on `library_path`).
- **SettingsModal / CategoryManagerModal**: config read/write (these
  are config editors, so direct config access makes sense).

### Reference patterns

Three Textual apps were surveyed:

- **toad** -- screens use `getters.app(ToadApp)` for typed access and
  call app methods directly (`self.app.settings.set()`,
  `self.app.save_settings()`). App owns persistence. Uses
  `data_bind()` to propagate reactive UI state from app to screens
  to widgets. No messages for persistence.
- **posting** -- modals return data via typed `dismiss()`, parent does
  I/O. Settings accessed via a `ContextVar` (no prop drilling).
  Models own their own `save_to_disk()` methods.
- **Bagels** -- screens do I/O directly in callbacks via stateless
  manager functions. Most coupled of the three.

The toad pattern -- typed app getter, direct method calls,
reactive propagation -- is the closest match for kist's needs.

## Decision

### 1. App owns config as reactive state

`KistApp` loads library config once at startup and exposes it as a
reactive attribute. Screens that need config (for form building,
category lists, etc.) read it from the app rather than loading it
themselves.

```python
class KistApp(App):
    library_path: reactive[Path | None] = reactive(None)
    library_config: reactive[LibraryConfig | None] = reactive(None)

    def _discover_library(self) -> None:
        result = find_library()
        self.library_path = result.library_root
        self.library_config = load_library_config(result.library_root)
```

When config changes (e.g. settings modal saves), the app reloads it
and the reactive system propagates the update.

### 2. Screens use typed app getter

Screens declare a typed app getter using Textual's `getters.app()`
instead of casting `self.app`:

```python
from textual import getters

class AddScreen(Screen):
    app = getters.app(KistApp)
```

This eliminates `# type: ignore` comments and provides proper type
checking. Screens can access `self.app.library_config` directly for
read-only config data like categories and separator.

### 3. Persistence via app methods

`KistApp` exposes methods for all part mutation operations. Screens
call these directly via the typed `self.app` getter. Errors propagate
via normal exceptions, so screens can handle them with try/except
and retain control over their own UI flow (clearing forms, showing
notifications).

```python
class KistApp(App):
    parts_version: reactive[int] = reactive(0)

    def save_part(self, part: Part, replacing: Ipn | None = None) -> None:
        """Persist a part and run the post-mutation pipeline."""
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        if replacing:
            db.remove(replacing)
        db.add(part)
        self._after_mutation()

    def delete_part(self, ipn: Ipn) -> None:
        """Remove a part and run the post-mutation pipeline."""
        db = PartsDatabase(self.library_path / "parts.json")
        db.load()
        db.remove(ipn)
        self._after_mutation()

    def _after_mutation(self) -> None:
        """Post-mutation side effects: sync, git, UI refresh."""
        if self.library_config:
            sync_symbols(self.library_path, ...)
        # git_commit(self.library_path, description)  # future
        self.parts_version += 1
```

Screens call these methods and handle errors locally:

```python
class AddScreen(Screen):
    app = getters.app(KistApp)

    def action_save(self) -> None:
        config = self.app.library_config
        part = build_part_from_form(d, config.categories, config.separator)
        try:
            self.app.save_part(part)
        except DuplicatePartError:
            self.notify(f"Already exists: {part.name}", severity="error")
            return
        self.notify(f"Saved: {part.name}")
        form.clear()
```

A message-based approach was considered and rejected. Messages
decouple the request from execution, but screens need synchronous
feedback to control their own UI flow (clearing forms on success,
showing specific error messages). Messages would require either
response messages or callbacks to flow errors back, adding
indirection without meaningful benefit. The toad reference app
validates that direct method calls scale to applications more
complex than kist.

### 4. Mutation pipeline

Every part mutation runs through `_after_mutation()`, which handles
side effects that screens should not know about:

- **Symbol sync** -- regenerate `.kicad_sym` files from the database.
- **Git commit** -- stage and commit changed files (future).
- **UI refresh** -- increment `parts_version` so watching screens
  reload.

This pipeline is the primary reason persistence must be centralised.
Adding a new post-mutation step (e.g. operation logging) requires a
change in one method, not in every screen.

### 5. Screen responsibilities

After this change, screens are responsible for:

- **Composing UI** -- layout, widgets, bindings
- **Form validation** -- checking required fields, calling
  `build_part_from_form()` with config from app
- **Calling app methods** -- `self.app.save_part()`,
  `self.app.delete_part()`, `self.app.save_library_config()`
- **Error handling** -- catching exceptions from app methods,
  notifying the user
- **Reacting to state changes** -- via reactive watchers

Screens are NOT responsible for:

- Loading config from disk
- Creating or managing database instances
- Knowing the library path (except for display purposes)
- Sync, git, or any post-mutation side effects

### 6. Config editors

SettingsModal manages two separate configs:

- **Global config** (theme) -- applied immediately via
  `self.app.theme`, persisted to the user config directory. Theme
  is the only global setting and is self-contained within the
  modal; no reactive attribute needed.
- **Library config** (prefix, separator, suppliers, directories) --
  saved via an app method (`self.app.save_library_config(config)`)
  so the app can update its reactive `library_config` and trigger
  downstream effects.

CategoryManagerModal modifies library config on each add/edit/delete.
It should receive config as a constructor argument for initial
display, rather than loading from disk in `on_mount`, and call the
app method to persist changes.

### 7. Database stays ephemeral

`PartsDatabase` instances are cheap (JSON file, sync I/O). The app
creates a fresh instance for each operation rather than holding a
long-lived connection. This avoids stale state when `parts.json`
is modified outside the TUI (by CLI commands or text editors).

`BrowseScreen` holds an in-memory snapshot (`_all_parts`) that may
diverge from disk if the CLI modifies `parts.json` externally. This
is acceptable -- the TUI is the primary editing interface during a
session, and external changes are picked up on next launch or when
`parts_version` changes. File watching can be added later if needed.

### 8. PartForm category source

`PartForm` currently builds its category `Select` options from the
hardcoded `WELL_KNOWN_CATEGORIES` constant rather than from library
config. As part of this refactor, the form must be updated to accept
categories as a parameter so it reflects the library's actual
category definitions. This also means `PartForm` needs to refresh
its options when `library_config` changes (e.g. after
CategoryManagerModal saves).

### 9. Async considerations

Symbol sync and git operations may be slow for large libraries. If
profiling shows `_after_mutation` blocks the UI, it can be converted
to a Textual `@work` method. The direct method call pattern supports
this -- `save_part` would become async and screens would `await` it,
or the post-mutation pipeline alone would be offloaded to a worker
while the screen receives its synchronous success/failure result
immediately.

## Consequences

### Positive

- Screens become presentation-only -- easier to test and reason about.
- The `# type: ignore[assignment]` pattern is eliminated.
- Config is loaded once and shared, not reloaded per operation.
- Database I/O is centralised in the app, making it trivial to add
  sync-on-save, git integration, and future post-mutation steps.
- Error handling stays in the screen via try/except -- no indirection.

### Negative

- Screens depend on `KistApp`'s method signatures. Renaming or
  changing a method requires updating callers (though
  `getters.app()` makes these usages easy to find).
- Config editors still need some direct config access, creating a
  slight asymmetry with other screens.

### Neutral

- Existing tests for screens need updating to mock app methods
  instead of mocking database access directly.

## Implementation

The refactor can be done incrementally:

1. Add `library_config` reactive and `parts_version` reactive to
   `KistApp`, load config on discovery.
2. Add `getters.app(KistApp)` to all screens and modals, removing
   `# type: ignore` casts.
3. Add `save_part()`, `delete_part()`, and `save_library_config()`
   methods to `KistApp` with `_after_mutation()` pipeline.
4. Migrate AddScreen to call `self.app.save_part()`. Update
   `PartForm` to accept categories as a parameter sourced from
   `self.app.library_config`.
5. Migrate DetailModal save/delete to call app methods.
6. Migrate BrowseScreen refresh to watch `parts_version` instead
   of relying on the DetailModal dismiss callback.
7. Migrate SettingsModal and CategoryManagerModal to call
   `self.app.save_library_config()`.
8. Move `_run_check` and `_run_sync` in `app.py` to use the
   reactive `library_config` instead of loading config from disk.
