"""Resolve user-supplied <id-or-slug> tokens to concrete file/dir paths.

Matching policy:
  1. Exact stem (slug) match → that file.
  2. Otherwise, substring match against stem.
  3. Zero matches → PKMNotFoundError.
  4. Multiple substring matches → PKMValidationError ("ambiguous").

Spec reference: §3.2 (capture/chunks set-status, show, rm).
"""
from __future__ import annotations

from pathlib import Path

from pkm.errors import PKMNotFoundError, PKMValidationError


def _captures_dir(root: Path) -> Path:
    return root / "data" / "raw" / "captures"


def _chunks_dir(root: Path) -> Path:
    return root / "data" / "raw" / "chunks"


def resolve_capture(root: Path, ref: str) -> Path:
    base = _captures_dir(root)
    if not base.exists():
        raise PKMNotFoundError(f"captures directory not found at {base.relative_to(root)}")
    files = list(base.glob("*.md"))
    # Exact stem match first
    exact = [p for p in files if p.stem == ref]
    if len(exact) == 1:
        return exact[0]
    # Substring match
    matches = [p for p in files if ref in p.stem]
    if not matches:
        raise PKMNotFoundError(
            f"no capture matches {ref!r}",
            hint="Try `pkm capture list` to see available slugs.",
        )
    if len(matches) > 1:
        names = ", ".join(p.stem for p in matches)
        raise PKMValidationError(
            f"ref {ref!r} is ambiguous: {names}",
            hint="Use a longer prefix or the full slug.",
        )
    return matches[0]


def resolve_chunk_topic(root: Path, topic: str) -> Path:
    base = _chunks_dir(root)
    target = base / topic
    if target.is_dir():
        return target
    raise PKMNotFoundError(
        f"no chunk topic named {topic!r}",
        hint="Try `pkm chunks list` to see topics.",
    )
