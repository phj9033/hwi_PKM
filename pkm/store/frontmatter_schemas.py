"""Frontmatter schemas for the four data buckets (spec §6.1).

M2 implements `capture` and `chunk`. `wiki` and `writing` land in M4/M5.

For each kind we expose:
- `<kind>_defaults(**overrides) -> dict`: build a fully-populated frontmatter
  dict ready for `frontmatter.serialize`.
- `validate_<kind>(fm)`: raise PKMValidationError if the dict is malformed.

Validation is **shape-only** here — referential checks (e.g. derived_from
exists) live in `pkm lint` (M4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from pkm.errors import PKMValidationError

_CAPTURE_REQUIRED = ("title", "slug", "created_at", "status", "source_type", "lang")
_CAPTURE_STATUSES = ("draft", "reviewed", "archived")
_CAPTURE_SOURCE_TYPES = ("url", "text", "research")
_CAPTURE_LANGS = ("ko", "en", "mixed")

_CHUNK_REQUIRED = ("topic", "created_at", "status", "lang", "sources")
_CHUNK_STATUSES = ("collecting", "curating", "ready")
_CHUNK_LANGS = ("ko", "en", "mixed")


def _now_iso() -> str:
    """Return the current local timestamp in ISO 8601 with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def capture_defaults(
    *,
    slug: str,
    title: str,
    source_url: str | None = None,
    status: str = "draft",
    lang: str = "ko",
    tags: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    """Build a frontmatter dict for a new capture."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "created_at": now,
        "status": status,
        "source_type": "url" if source_url else "text",
        "lang": lang,
        "tags": list(tags) if tags else [],
    }
    if source_url:
        fm["source_url"] = source_url
        fm["fetched_at"] = now
    if summary:
        fm["summary"] = summary
    return fm


def chunk_defaults(
    *,
    topic: str,
    status: str = "collecting",
    lang: str = "mixed",
    description: str | None = None,
    sources: Iterable[str] | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Build a frontmatter dict for a new chunk README."""
    fm: dict = {
        "topic": topic,
        "created_at": _now_iso(),
        "status": status,
        "lang": lang,
        "sources": list(sources) if sources else [],
        "tags": list(tags) if tags else [],
    }
    if description:
        fm["description"] = description
    return fm


def _check_required(fm: dict, required: tuple[str, ...], kind: str) -> None:
    missing = [k for k in required if k not in fm]
    if missing:
        raise PKMValidationError(
            f"{kind} frontmatter missing required field(s): {', '.join(missing)}",
            hint=f"Required for {kind}: {', '.join(required)}",
        )


def _check_enum(fm: dict, key: str, allowed: tuple[str, ...], kind: str) -> None:
    val = fm.get(key)
    if val not in allowed:
        raise PKMValidationError(
            f"{kind} frontmatter {key}={val!r} not in {allowed}",
            hint=f"Allowed values: {', '.join(allowed)}",
        )


def validate_capture(fm: dict) -> None:
    _check_required(fm, _CAPTURE_REQUIRED, "capture")
    _check_enum(fm, "status", _CAPTURE_STATUSES, "capture")
    _check_enum(fm, "source_type", _CAPTURE_SOURCE_TYPES, "capture")
    _check_enum(fm, "lang", _CAPTURE_LANGS, "capture")


def validate_chunk(fm: dict) -> None:
    _check_required(fm, _CHUNK_REQUIRED, "chunk")
    _check_enum(fm, "status", _CHUNK_STATUSES, "chunk")
    _check_enum(fm, "lang", _CHUNK_LANGS, "chunk")
    if not isinstance(fm.get("sources"), list):
        raise PKMValidationError("chunk frontmatter `sources` must be a list")
