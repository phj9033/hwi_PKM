"""DashboardContext - single object passed to every page builder.

Grown in M6.11; the seed shape lands here so M6.5-M6.10 can build against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pkm.dashboard.scanner import DocRegistry


@dataclass
class DashboardContext:
    root: Path
    registry: DocRegistry
    lint_summary: dict[str, Any] | None = None  # parsed `pkm lint --json`
    doctor: dict[str, Any] | None = None  # parsed `pkm doctor --json`
    config_masked: dict[str, Any] | None = None
    recent_log: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "strict"
