"""Path helpers for data/projects/** (V3)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


CATEGORIES = ("decisions", "pitfalls", "snippets", "qna", "notes")
PROJECT_ID_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def projects_root(repo: Path) -> Path:
    return repo / "data" / "projects"


def project_dir(repo: Path, pid: str) -> Path:
    return projects_root(repo) / pid


def project_index(repo: Path, pid: str) -> Path:
    return project_dir(repo, pid) / "index.md"


def project_category_dir(repo: Path, pid: str, category: str) -> Path:
    if category not in CATEGORIES:
        raise ValueError(f"invalid category: {category!r}")
    return project_dir(repo, pid) / category


def slug_for_knowledge(title: str, *, today: date | None = None) -> str:
    """`YYYY-MM-DD-<title-slugified>`. Idempotent on already-prefixed slugs."""
    today = today or date.today()
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{today.isoformat()}-{base}"


def is_valid_project_id(pid: str) -> bool:
    return bool(PROJECT_ID_RX.match(pid)) and len(pid) <= 64
