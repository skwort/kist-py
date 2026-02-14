"""Library health checks -- name drift and duplicate identity detection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from kist.core.database import PartsDatabase
from kist.core.naming import generate_name, get_identity
from kist.models.config import LibraryConfig


@dataclass
class CheckIssue:
    """A single issue found during library validation."""

    kind: str  # "name_drift" | "duplicate_identity"
    message: str
    parts: list[str]


def check_library(db: PartsDatabase, config: LibraryConfig) -> list[CheckIssue]:
    """
    Validate part names and check for identity duplicates.

    Returns a list of issues found. An empty list means the library is clean.
    """
    parts = db.list_parts()
    if not parts:
        return []

    issues: list[CheckIssue] = []
    categories = config.categories

    # Single pass: check name drift and build identity map
    by_identity: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for part in parts:
        expected = generate_name(part, categories, config.separator)
        if part.name != expected:
            issues.append(
                CheckIssue(
                    kind="name_drift",
                    message=f'"{part.name}" should be "{expected}"',
                    parts=[part.name],
                )
            )
        by_identity[get_identity(part, categories)].append(part.name)

    for identity, names in by_identity.items():
        if len(names) > 1:
            joined = " and ".join(names)
            issues.append(
                CheckIssue(
                    kind="duplicate_identity",
                    message=f"{joined} share {identity}",
                    parts=list(names),
                )
            )

    return issues
