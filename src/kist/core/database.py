"""JSON-backed parts database."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pydantic import TypeAdapter

from kist.errors import DatabaseError, DuplicatePartError
from kist.models import Ipn, Part, ProprietaryPart, SemiJellybeanPart

# TypeAdapter provides validate/serialize for the Part discriminated union,
# which is a type alias (not a BaseModel subclass) and has no .model_validate().
# Instantiated once at module level to avoid recompiling the schema per call.
_part_adapter = TypeAdapter(Part)


def create_empty(path: Path) -> None:
    """Write a minimal empty parts database to *path*."""
    data = {"version": 1, "parts": {}}
    path.write_text(json.dumps(data, indent=2) + "\n")


class PartsDatabase:
    """CRUD interface over a ``parts.json`` file.

    The file is the source of truth -- every mutation saves immediately.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._parts: dict[Ipn, Part] = {}
        self._name_index: dict[str, Ipn] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def parts(self) -> dict[Ipn, Part]:
        """Return a shallow copy of the internal parts dict."""
        return dict(self._parts)

    # -- Persistence ---------------------------------------------------------

    def load(self) -> None:
        """Read and validate the JSON database from disk."""
        try:
            raw = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise DatabaseError(f"Failed to load {self._path}: {exc}") from exc

        parts: dict[Ipn, Part] = {}
        for uid, part_data in raw.get("parts", {}).items():
            part = _part_adapter.validate_python(part_data)
            part.ipn = Ipn(uid)
            parts[Ipn(uid)] = part

        self._parts = parts
        self._name_index = {part.name: uid for uid, part in parts.items()}

    def save(self) -> None:
        """Write the database to disk, sorted by part name."""
        data = {
            "version": 1,
            "parts": {
                uid: _part_adapter.dump_python(part, mode="json", exclude_none=True)
                for uid, part in sorted(
                    self._parts.items(), key=lambda item: item[1].name
                )
            },
        }
        try:
            # NOTE: no sort_keys -- Pydantic preserves field-declaration
            # order, which matches the logical reading order from ADR-001.
            self._path.write_text(json.dumps(data, indent=2) + "\n")
        except OSError as exc:
            raise DatabaseError(f"Failed to save {self._path}: {exc}") from exc

    # -- CRUD ----------------------------------------------------------------

    def add(self, part: Part) -> Ipn:
        """
        Add a part, returning its generated IPN.

        Raises :class:`DuplicatePartError` if the name is already taken.
        """
        if part.name in self._name_index:
            raise DuplicatePartError(f"Part name already exists: {part.name}")

        ipn = Ipn(str(uuid.uuid4()))
        part.ipn = ipn
        self._parts[ipn] = part
        self._name_index[part.name] = ipn
        self.save()
        return ipn

    def remove(self, ipn: Ipn) -> Part | None:
        """Remove a part by IPN, returning it (or ``None`` if not found)."""
        part = self._parts.pop(ipn, None)
        if part is not None:
            self._name_index.pop(part.name, None)
            self.save()
        return part

    def get(self, ipn: Ipn) -> Part | None:
        """Look up a part by IPN, returning ``None`` if not found."""
        return self._parts.get(ipn)

    def resolve(self, name: str) -> Ipn | None:
        """Resolve a part name to its IPN, returning ``None`` if not found."""
        return self._name_index.get(name)

    def list_parts(self) -> list[Part]:
        """Return all parts sorted by name."""
        return sorted(self._parts.values(), key=lambda p: p.name)

    def search(self, query: str) -> list[Part]:
        """Substring search across name, description, tags, mpn, and base_pn."""
        q = query.lower()
        results: list[Part] = []
        for part in self._parts.values():
            if self._matches(part, q):
                results.append(part)
        return sorted(results, key=lambda p: p.name)

    # -- Internals -----------------------------------------------------------

    @staticmethod
    def _matches(part: Part, query: str) -> bool:
        if query in part.name.lower():
            return True
        if query in part.description.lower():
            return True
        if any(query in tag.lower() for tag in part.tags):
            return True
        if isinstance(part, (ProprietaryPart, SemiJellybeanPart)):
            if query in part.mpn.lower():
                return True
        if isinstance(part, SemiJellybeanPart):
            if query in part.base_pn.lower():
                return True
        return False
