"""Style sample path helpers.

Layout: ``data/style/<style>/<sample>.md`` — each style is a directory with
1+ samples. Mirrors `pkm.store.wiki_paths` in spirit but with a fixed 2-level
shape (style / sample). Flat files at ``data/style/<name>.md`` are NOT a
valid sample location; the lint rule ``STYLE_FLAT_FILE`` surfaces them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError

__all__ = [
    "iter_all_style",
    "iter_style_samples",
    "iter_styles",
    "resolve_style",
    "style_dir",
    "style_path",
    "style_root",
]


def style_dir(root: Path) -> Path:
    """Return the top-level style directory."""
    return root / "data" / "style"


def style_root(root: Path, style: str) -> Path:
    """Return the directory that holds samples for one style."""
    return style_dir(root) / style


def style_path(root: Path, style: str, sample: str) -> Path:
    """Return the canonical path for a sample (without checking existence)."""
    return style_root(root, style) / f"{sample}.md"


def iter_styles(root: Path) -> Iterator[Path]:
    """Yield each style directory under data/style/ (sorted)."""
    base = style_dir(root)
    if not base.exists():
        return
    for p in sorted(base.iterdir()):
        if p.is_dir():
            yield p


def iter_style_samples(root: Path, style: str) -> Iterator[Path]:
    """Yield every sample .md file under one style directory (sorted)."""
    sr = style_root(root, style)
    if not sr.exists() or not sr.is_dir():
        return
    yield from sorted(sr.glob("*.md"))


def iter_all_style(root: Path) -> Iterator[Path]:
    """Yield every sample .md file under data/style/<style>/ (sorted).

    Flat files at data/style/<name>.md are intentionally skipped — the lint
    rule STYLE_FLAT_FILE surfaces them separately.
    """
    base = style_dir(root)
    if not base.exists():
        return
    yield from sorted(base.glob("*/*.md"))


def resolve_style(root: Path, ref: str) -> Path:
    """Resolve a user-supplied sample reference to a Path.

    Accepted forms:
      1. Full path: 'data/style/<style>/<sample>.md'
      2. Bare 'style/sample' shorthand

    Form 1 deliberately does NOT call `.resolve()` so callers can do
    `target.relative_to(root)` with a relative root (e.g. `--root .`).
    Same regression class as wiki_paths.py:61.
    """
    if "/" in ref and ref.endswith(".md"):
        p = root / ref
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(f"style sample not found: {ref}")

    if "/" in ref and not ref.endswith(".md"):
        style, _, sample = ref.partition("/")
        if style and sample and "/" not in sample:
            p = style_path(root, style, sample)
            if p.exists() and p.is_file():
                return p
            raise PKMNotFoundError(
                f"no style sample named {ref!r}",
                hint=f"Try `ls data/style/{style}/` to see available samples.",
            )

    if "/" in ref:
        raise PKMNotFoundError(
            f"cannot resolve style ref {ref!r}",
            hint="Use '<style>/<sample>' — only one slash is allowed.",
        )
    raise PKMNotFoundError(
        f"cannot resolve style ref {ref!r}",
        hint="Use '<style>/<sample>' or 'data/style/<style>/<sample>.md'.",
    )
