"""Auto-generated TOC for `data/index.md`.

Regenerated whole on every mutation. Layout:

    # Index

    _Auto-generated. Do not edit by hand._

    ## Captures
    - [<slug>](raw/captures/<slug>.md) — <title> [<status>]
    ...

    ## Chunks
    - [<topic>](raw/chunks/<topic>/README.md) — <description> [<status>]
    ...

    ## Wiki
    _(empty until M4)_

    ## Writing
    _(empty until M5)_

Spec reference: §2 (index.md), §6.6 (auto-update).
"""
from __future__ import annotations

from pathlib import Path

from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse

_INDEX_REL = "data/index.md"

_HEADER = "# Index\n\n_Auto-generated. Do not edit by hand._\n"


def _safe_parse(path: Path) -> tuple[dict, str]:
    """Parse a file's frontmatter; return ({}, "") on any error."""
    try:
        fm, body = parse(path.read_text(encoding="utf-8"))
        return fm, body
    except Exception:
        return {}, ""


def _captures_section(root: Path) -> str:
    captures_dir = root / "data" / "raw" / "captures"
    if not captures_dir.exists():
        return "_(none)_\n"
    rows: list[str] = []
    for path in sorted(captures_dir.glob("*.md")):
        fm, _ = _safe_parse(path)
        slug = fm.get("slug") or path.stem
        title = fm.get("title") or "(no title)"
        status = fm.get("status") or "?"
        rel = path.relative_to(root / "data").as_posix()
        rows.append(f"- [{slug}]({rel}) — {title} [{status}]")
    if not rows:
        return "_(none)_\n"
    return "\n".join(rows) + "\n"


def _chunks_section(root: Path) -> str:
    chunks_dir = root / "data" / "raw" / "chunks"
    if not chunks_dir.exists():
        return "_(none)_\n"
    rows: list[str] = []
    for topic_dir in sorted(p for p in chunks_dir.iterdir() if p.is_dir()):
        readme = topic_dir / "README.md"
        if not readme.exists():
            rows.append(f"- {topic_dir.name} — (no README.md) [?]")
            continue
        fm, _ = _safe_parse(readme)
        topic = fm.get("topic") or topic_dir.name
        desc = fm.get("description") or ""
        status = fm.get("status") or "?"
        rel = readme.relative_to(root / "data").as_posix()
        rows.append(f"- [{topic}]({rel}) — {desc} [{status}]")
    if not rows:
        return "_(none)_\n"
    return "\n".join(rows) + "\n"


def rebuild_index(root: Path) -> None:
    """Regenerate `data/index.md` from the filesystem state."""
    sections = [
        _HEADER,
        "## Captures",
        _captures_section(root),
        "## Chunks",
        _chunks_section(root),
        "## Wiki",
        "_(empty until M4)_",
        "## Writing",
        "_(empty until M5)_",
        "",
    ]
    text = "\n".join(sections)
    atomic_write(root / _INDEX_REL, text)
