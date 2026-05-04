"""Wiki path helpers shared by promote / demote / wiki edit / lint.

`WIKI_BUCKETS` is owned by `pkm.store.frontmatter_schemas` (the schema
module is the single source of truth). We re-export it here so callers
that already think in path terms (`promote.py`, `demote.py`, etc.) don't
need to reach into the schemas module.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store.frontmatter_schemas import WIKI_BUCKETS  # re-export

__all__ = [
    "WIKI_BUCKETS",
    "iter_all_wiki",
    "resolve_wiki",
    "wiki_dir",
    "wiki_path",
]


def wiki_dir(root: Path, bucket: str) -> Path:
    """Return the directory for a wiki bucket. Does not validate existence."""
    return root / "data" / "wiki" / bucket


def wiki_path(root: Path, bucket: str, slug: str) -> Path:
    """Return the canonical path for a wiki page (without checking existence)."""
    return wiki_dir(root, bucket) / f"{slug}.md"


def iter_all_wiki(root: Path) -> Iterator[Path]:
    """Yield every wiki .md file under data/wiki/<bucket>/."""
    base = root / "data" / "wiki"
    if not base.exists():
        return
    for bucket in WIKI_BUCKETS:
        d = base / bucket
        if not d.exists():
            continue
        yield from sorted(d.glob("*.md"))


def resolve_wiki(root: Path, ref: str) -> Path:
    """Resolve a user-supplied wiki reference to a Path.

    Accepted forms:
      1. Full path: 'data/wiki/<bucket>/<slug>.md'
      2. Bucket/slug shorthand: '<bucket>/<slug>'
      3. Bare slug: '<slug>' — must be unique across all buckets

    Raises PKMNotFoundError if nothing matches, PKMValidationError if a
    bare slug is ambiguous across buckets.
    """
    # Form 1: path-like
    if "/" in ref and ref.endswith(".md"):
        # Don't .resolve() here — callers do `target.relative_to(root)` and
        # if root is relative (e.g. default `--root .`) while target is
        # absolute, that call raises ValueError. Forms 2 & 3 already preserve
        # root's relativity; keep Form 1 consistent.
        p = root / ref
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(
            f"wiki page not found: {ref}",
            hint=f"Expected under data/wiki/<bucket>/. Buckets: {', '.join(WIKI_BUCKETS)}",
        )

    # Form 2: <bucket>/<slug>
    if "/" in ref:
        bucket, slug = ref.split("/", 1)
        if bucket in WIKI_BUCKETS:
            p = wiki_path(root, bucket, slug)
            if p.exists():
                return p
            raise PKMNotFoundError(
                f"wiki page not found: {bucket}/{slug}",
                hint=f"Try `ls data/wiki/{bucket}/`",
            )

    # Form 3: bare slug
    matches = [p for p in iter_all_wiki(root) if p.stem == ref]
    if not matches:
        raise PKMNotFoundError(
            f"no wiki page named {ref!r}",
            hint=f"Buckets: {', '.join(WIKI_BUCKETS)}. Try `pkm search {ref}`.",
        )
    if len(matches) > 1:
        names = ", ".join(p.relative_to(root).as_posix() for p in matches)
        raise PKMValidationError(
            f"wiki ref {ref!r} is ambiguous: {names}",
            hint="Pass <bucket>/<slug> or full path.",
        )
    return matches[0]
