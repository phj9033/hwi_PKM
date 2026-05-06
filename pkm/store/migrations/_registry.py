"""Migration module dataclass + helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationModule:
    """One registered migration, loaded from a `m<NNN>_*.py` file."""

    id: int
    description: str
    depends_on_extra: str | None
    check_fn: Callable[..., dict]
    apply_fn: Callable[..., dict]
