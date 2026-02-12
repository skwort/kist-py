"""Kist error hierarchy."""


class KistError(Exception):
    """Base exception for all kist errors."""


class PartNotFoundError(KistError):
    """Raised when a part cannot be found by name or ID."""


class DuplicatePartError(KistError):
    """Raised when adding a part with a name that already exists."""


class DatabaseError(KistError):
    """Raised for JSON database read/write failures."""


class LibraryNotFoundError(KistError):
    """Raised when library discovery exhausts all parent directories."""


class LibraryExistsError(KistError):
    """Raised when initialising or linking in an already-configured directory."""


class ConfigError(KistError):
    """Raised for corrupt, missing, or invalid configuration files."""


class ProviderError(KistError):
    """Base exception for supplier provider failures."""


class DigiKeyError(ProviderError):
    """Raised when the DigiKey API returns an error or credentials are missing."""
