"""Kist error hierarchy."""


class KistError(Exception):
    """Base exception for all kist errors."""


class PartNotFoundError(KistError):
    """Raised when a part cannot be found by name or ID."""


class DuplicatePartError(KistError):
    """Raised when adding a part with a name that already exists."""


class DatabaseError(KistError):
    """Raised for JSON database read/write failures."""
