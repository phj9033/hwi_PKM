"""Frontmatter schemas for the five data buckets (spec §6.1).

M2 implements `capture` and `chunk`. `wiki` and `writing` land in M4/M5.
M8 adds `style` (blog sample corpus).

For each kind we expose:
- `<kind>_defaults(**overrides) -> dict`: build a fully-populated frontmatter
  dict ready for `frontmatter.serialize`.
- `validate_<kind>(fm)`: raise PKMValidationError if the dict is malformed.

Validation is **shape-only** here — referential checks (e.g. derived_from
exists) live in `pkm lint` (M4).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

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
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


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


# --- wiki ---

_WIKI_REQUIRED = ("title", "slug", "bucket", "created_at", "updated_at", "status", "lang", "tags")
_WIKI_BUCKETS = ("concepts", "entities", "notes", "reports")
_WIKI_STATUSES = ("stub", "active", "deprecated")
_WIKI_LANGS = ("ko", "en", "mixed")


def wiki_defaults(
    *,
    slug: str,
    title: str,
    bucket: str,
    status: str = "stub",
    lang: str = "ko",
    tags: list[str] | None = None,
    promoted_from: str | None = None,
    derived_from: list[str] | None = None,
    related: list[str] | None = None,
) -> dict:
    """Build a frontmatter dict for a new wiki page."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "bucket": bucket,
        "created_at": now,
        "updated_at": now,
        "status": status,
        "lang": lang,
        "tags": list(tags) if tags else [],
    }
    if promoted_from:
        fm["promoted_from"] = promoted_from
    if derived_from:
        fm["derived_from"] = list(derived_from)
    if related:
        fm["related"] = list(related)
    return fm


def validate_wiki(fm: dict) -> None:
    _check_required(fm, _WIKI_REQUIRED, "wiki")
    _check_enum(fm, "bucket", _WIKI_BUCKETS, "wiki")
    _check_enum(fm, "status", _WIKI_STATUSES, "wiki")
    _check_enum(fm, "lang", _WIKI_LANGS, "wiki")
    if not isinstance(fm.get("tags"), list):
        raise PKMValidationError("wiki frontmatter `tags` must be a list")


# --- writing ---

_WRITING_REQUIRED = (
    "title",
    "slug",
    "created_at",
    "updated_at",
    "status",
    "purpose",
    "derived_from",
    "lang",
    "tags",
)
_WRITING_PURPOSES = ("guideline", "report", "summary", "essay")
_WRITING_STATUSES = ("draft", "final", "promoted", "abandoned")
_WRITING_LANGS = ("ko", "en", "mixed")


def writing_defaults(
    *,
    slug: str,
    title: str,
    purpose: str,
    derived_from: list[str],
    status: str = "draft",
    lang: str = "ko",
    tags: list[str] | None = None,
    search_seed: str | None = None,
) -> dict:
    """Build a frontmatter dict for a new writing artifact."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "created_at": now,
        "updated_at": now,
        "status": status,
        "purpose": purpose,
        "derived_from": list(derived_from),
        "lang": lang,
        "tags": list(tags) if tags else [],
    }
    if search_seed:
        fm["search_seed"] = search_seed
    return fm


def validate_writing(fm: dict) -> None:
    _check_required(fm, _WRITING_REQUIRED, "writing")
    _check_enum(fm, "purpose", _WRITING_PURPOSES, "writing")
    _check_enum(fm, "status", _WRITING_STATUSES, "writing")
    _check_enum(fm, "lang", _WRITING_LANGS, "writing")
    derived = fm.get("derived_from")
    if not isinstance(derived, list) or not derived:
        raise PKMValidationError(
            "writing frontmatter `derived_from` must be a non-empty list",
            hint="A writing artifact must trace back to at least one source.",
        )


# --- style (M8) ---

_STYLE_REQUIRED = ("title", "slug", "lang", "created_at", "updated_at")
_STYLE_LANGS = ("ko", "en", "mixed")


def style_defaults(
    *,
    slug: str,
    title: str,
    lang: str = "ko",
    tags: list[str] | None = None,
    source_url: str | None = None,
    source_path: str | None = None,
) -> dict:
    """Build a frontmatter dict for a new style sample."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "lang": lang,
        "created_at": now,
        "updated_at": now,
        "tags": list(tags) if tags else [],
    }
    if source_url:
        fm["source_url"] = source_url
    if source_path:
        fm["source_path"] = source_path
    return fm


def validate_style(fm: dict) -> None:
    _check_required(fm, _STYLE_REQUIRED, "style")
    _check_enum(fm, "lang", _STYLE_LANGS, "style")
    if not isinstance(fm.get("tags"), list):
        raise PKMValidationError("style frontmatter `tags` must be a list")


# Public aliases — `pkm.lint.rules` consumes these to avoid importing
# underscore-prefixed names. The underscore versions remain the internal
# module-level reference for the validators above.
CAPTURE_REQUIRED = _CAPTURE_REQUIRED
CAPTURE_STATUSES = _CAPTURE_STATUSES
CAPTURE_SOURCE_TYPES = _CAPTURE_SOURCE_TYPES
CAPTURE_LANGS = _CAPTURE_LANGS
CHUNK_REQUIRED = _CHUNK_REQUIRED
CHUNK_STATUSES = _CHUNK_STATUSES
CHUNK_LANGS = _CHUNK_LANGS
WIKI_REQUIRED = _WIKI_REQUIRED
WIKI_BUCKETS = _WIKI_BUCKETS
WIKI_STATUSES = _WIKI_STATUSES
WIKI_LANGS = _WIKI_LANGS
WRITING_REQUIRED = _WRITING_REQUIRED
WRITING_PURPOSES = _WRITING_PURPOSES
WRITING_STATUSES = _WRITING_STATUSES
WRITING_LANGS = _WRITING_LANGS
STYLE_REQUIRED = _STYLE_REQUIRED
STYLE_LANGS = _STYLE_LANGS
