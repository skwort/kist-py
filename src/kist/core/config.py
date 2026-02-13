"""Configuration I/O and resolution."""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs
import tomlkit
import tomlkit.exceptions

from kist.errors import ConfigError
from kist.models.config import GlobalConfig, LibraryConfig, ProjectRef
from kist.providers.models import ProviderMappingConfig

KIST_MARKER = ".kist"
PROJECT_REF = "kist.toml"
LIBRARY_CONFIG = "config.toml"


def _get_config_dir() -> Path:
    """Return the global config directory, respecting KIST_CONFIG_DIR."""
    env = os.environ.get("KIST_CONFIG_DIR")
    if env:
        return Path(env)
    return Path(platformdirs.user_config_dir("kist"))


def load_global_config() -> GlobalConfig:
    """Load global config, returning defaults if the file is absent."""
    path = _get_config_dir() / LIBRARY_CONFIG
    if not path.exists():
        return GlobalConfig()
    try:
        data = tomlkit.loads(path.read_text())
        return GlobalConfig.model_validate(dict(data))
    except (OSError, tomlkit.exceptions.ParseError) as exc:
        raise ConfigError(f"Failed to read global config {path}: {exc}") from exc


def resolve_init_config(**overrides: str | list[str] | None) -> LibraryConfig:
    """Merge built-in defaults, global config, and CLI overrides."""
    global_cfg = load_global_config()
    merged = global_cfg.model_dump()
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return LibraryConfig.model_validate(merged)


def load_library_config(library_root: Path) -> LibraryConfig:
    """Read .kist/config.toml from a library root."""
    path = library_root / KIST_MARKER / LIBRARY_CONFIG
    if not path.exists():
        raise ConfigError(f"Library config not found: {path}")
    try:
        data = tomlkit.loads(path.read_text())
        return LibraryConfig.model_validate(dict(data))
    except (OSError, tomlkit.exceptions.ParseError) as exc:
        raise ConfigError(f"Failed to read library config {path}: {exc}") from exc


def _strip_category_defaults(data: dict) -> dict:
    """Remove empty containers and default values from category defs.

    tomlkit can't serialize None, and empty lists/dicts are noise in
    the TOML output. The default value_field_separator "/" is also
    stripped to keep config clean.
    """
    cats = data.get("categories")
    if not cats:
        return data
    cleaned: dict = {}
    for code, cat in cats.items():
        cleaned[code] = {
            k: v
            for k, v in cat.items()
            if v is not None
            and v != []
            and v != {}
            and not (k == "value_field_separator" and v == "/")
        }
    data["categories"] = cleaned
    return data


def save_library_config(library_root: Path, config: LibraryConfig) -> None:
    """Write config to .kist/config.toml, creating .kist/ if needed."""
    kist_dir = library_root / KIST_MARKER
    kist_dir.mkdir(parents=True, exist_ok=True)
    path = kist_dir / LIBRARY_CONFIG
    data = _strip_category_defaults(config.model_dump(exclude_none=True))
    doc = tomlkit.dumps(data)
    path.write_text(doc)


def load_project_ref(path: Path) -> ProjectRef:
    """Read a kist.toml project reference."""
    if not path.exists():
        raise ConfigError(f"Project reference not found: {path}")
    try:
        data = tomlkit.loads(path.read_text())
        return ProjectRef.model_validate(dict(data))
    except (OSError, tomlkit.exceptions.ParseError) as exc:
        raise ConfigError(f"Failed to read project reference {path}: {exc}") from exc


def save_project_ref(path: Path, ref: ProjectRef) -> None:
    """Write a kist.toml project reference."""
    doc = tomlkit.dumps(ref.model_dump())
    path.write_text(doc)


# -- Provider mapping config ------------------------------------------------

# Lazy import to avoid circular deps at module level
_PROVIDER_DEFAULTS: dict[str, str] = {
    "digikey": "kist.providers.digikey",
}


def load_provider_mapping(provider_name: str) -> ProviderMappingConfig:
    """
    Load mapping config for a provider, merging user TOML over defaults.

    If no TOML file exists, returns the provider's built-in defaults.
    Dict fields (categories, parameters, mounting) are merged key-by-key.
    List fields (ignore_parameters) and scalars are replaced entirely
    if present in the TOML.
    """
    # Load built-in defaults from the provider module
    module_path = _PROVIDER_DEFAULTS.get(provider_name)
    if module_path is None:
        raise ConfigError(f"Unknown provider: {provider_name}")

    import importlib

    mod = importlib.import_module(module_path)
    defaults: ProviderMappingConfig = mod.default_mapping()

    # Check for user overrides
    toml_path = _get_config_dir() / "providers" / f"{provider_name}.toml"
    if not toml_path.exists():
        return defaults

    try:
        user_data = dict(tomlkit.loads(toml_path.read_text()))
    except (OSError, tomlkit.exceptions.ParseError) as exc:
        raise ConfigError(f"Failed to read provider config {toml_path}: {exc}") from exc

    # Merge: dicts overlay key-by-key, lists/scalars replace
    merged = defaults.model_dump()
    for key, value in user_data.items():
        if key not in merged:
            continue  # ignore unknown keys
        if isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return ProviderMappingConfig.model_validate(merged)
