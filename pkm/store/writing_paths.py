"""Slug ↔ path helpers for data/writing/.

Mirrors pkm/store/wiki_paths.py from M4. Writing is a flat directory
(no buckets) — slug is unique under data/writing/.
"""

from __future__ import annotations

from pathlib import Path

WRITING_DIR = Path("data") / "writing"


def writing_path(root: Path, slug: str) -> Path:
    return root / WRITING_DIR / f"{slug}.md"


def resolve_writing(root: Path, ref: str) -> Path:
    """Accepts: bare slug, data/writing/<slug>.md, or absolute path."""
    p = Path(ref)
    if p.is_absolute():
        return p
    if p.suffix == ".md" and p.parts[:2] == ("data", "writing"):
        return root / p
    return writing_path(root, ref)


def list_writing(root: Path) -> list[Path]:
    d = root / WRITING_DIR
    if not d.exists():
        return []
    return sorted(d.glob("*.md"))
