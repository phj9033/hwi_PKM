"""Style sample path helpers.

Mirrors `pkm.store.wiki_paths` but flat — `data/style/<slug>.md` with no
sub-buckets. M8 brainstorm decision #2.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError

__all__ = ["iter_all_style", "resolve_style", "style_dir", "style_path"]


def style_dir(root: Path) -> Path:
    """Return the directory that holds style samples."""
    return root / "data" / "style"


def style_path(root: Path, slug: str) -> Path:
    """Return the canonical path for a style sample (without checking existence)."""
    return style_dir(root) / f"{slug}.md"


def iter_all_style(root: Path) -> Iterator[Path]:
    """Yield every style sample .md file under data/style/."""
    base = style_dir(root)
    if not base.exists():
        return
    yield from sorted(base.glob("*.md"))


def resolve_style(root: Path, ref: str) -> Path:
    """Resolve a user-supplied style reference to a Path.

    Accepted forms:
      1. Full path: 'data/style/<slug>.md'
      2. Bare slug: '<slug>'

    Form 1 deliberately does NOT call `.resolve()` so callers can do
    `target.relative_to(root)` with a relative root (e.g. `--root .`).
    Same regression class as wiki_paths.py:61.
    """
    if "/" in ref and ref.endswith(".md"):
        p = root / ref
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(f"style sample not found: {ref}")

    p = style_path(root, ref)
    if p.exists() and p.is_file():
        return p
    raise PKMNotFoundError(
        f"no style sample named {ref!r}",
        hint="Try `ls data/style/` to see available slugs.",
    )
