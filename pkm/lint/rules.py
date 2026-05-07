"""Lint rules — pure detection (no mutation).

14 rules: 7 errors + 7 warnings. Each returns Iterator[LintFinding]. The
CLI orchestrator (commands/lint.py) calls `collect_findings(root)`.

Spec reference: §6.5.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pkm.errors import PKMValidationError
from pkm.store.frontmatter import parse
from pkm.store.frontmatter_schemas import (
    CAPTURE_LANGS,
    CAPTURE_REQUIRED,
    CAPTURE_SOURCE_TYPES,
    CAPTURE_STATUSES,
    CHUNK_LANGS,
    CHUNK_REQUIRED,
    CHUNK_STATUSES,
    STYLE_LANGS,
    STYLE_REQUIRED,
    WIKI_BUCKETS,
    WIKI_LANGS,
    WIKI_REQUIRED,
    WIKI_STATUSES,
    WRITING_LANGS,
    WRITING_PURPOSES,
    WRITING_REQUIRED,
    WRITING_STATUSES,
)

_STALE_DRAFT_DAYS = 30
_STALE_STUB_DAYS = 30
_LARGE_CHUNK_DAYS = 60

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
_CITATION_RE = re.compile(r"\[[^\]]+\]\((data/[^)]+)\)")
_HANGUL_RE = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class LintFinding:
    code: str
    severity: str  # "error" | "warning"
    path: str  # repo-relative
    message: str
    field: str | None = None
    fixable: bool = False


@dataclass
class _Doc:
    """Pre-parsed snapshot row."""

    path: Path
    rel: str
    kind: str  # "capture" | "chunk" | "wiki" | "writing" | "style"
    fm: dict
    body: str
    mtime: float
    parse_error: str | None = None


@dataclass
class _Snapshot:
    docs: list[_Doc] = field(default_factory=list)

    def by_kind(self, kind: str) -> list[_Doc]:
        return [d for d in self.docs if d.kind == kind]


def _kind_for(rel: str) -> str | None:
    if rel.startswith("data/raw/captures/") and rel.endswith(".md"):
        return "capture"
    if rel.startswith("data/raw/chunks/") and rel.endswith("/README.md"):
        return "chunk"
    if rel.startswith("data/wiki/") and rel.endswith(".md"):
        return "wiki"
    if rel.startswith("data/writing/") and rel.endswith(".md"):
        return "writing"
    if rel.startswith("data/style/") and rel.endswith(".md"):
        return "style"
    return None


def _load_snapshot(root: Path) -> _Snapshot:
    snap = _Snapshot()
    data = root / "data"
    if not data.exists():
        return snap
    for p in sorted(data.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        kind = _kind_for(rel)
        if kind is None:
            continue
        try:
            fm, body = parse(p.read_text(encoding="utf-8"))
            err = None
        except PKMValidationError as e:
            fm, body, err = {}, "", str(e)
        snap.docs.append(
            _Doc(
                path=p,
                rel=rel,
                kind=kind,
                fm=fm,
                body=body,
                mtime=p.stat().st_mtime,
                parse_error=err,
            )
        )
    return snap


# --------- Errors ---------

_REQUIRED_BY_KIND = {
    "capture": CAPTURE_REQUIRED,
    "chunk": CHUNK_REQUIRED,
    "wiki": WIKI_REQUIRED,
    "writing": WRITING_REQUIRED,
    "style": STYLE_REQUIRED,
}

_ENUMS_BY_KIND = {
    "capture": [
        ("status", CAPTURE_STATUSES),
        ("source_type", CAPTURE_SOURCE_TYPES),
        ("lang", CAPTURE_LANGS),
    ],
    "chunk": [("status", CHUNK_STATUSES), ("lang", CHUNK_LANGS)],
    "wiki": [
        ("bucket", WIKI_BUCKETS),
        ("status", WIKI_STATUSES),
        ("lang", WIKI_LANGS),
    ],
    "writing": [
        ("purpose", WRITING_PURPOSES),
        ("status", WRITING_STATUSES),
        ("lang", WRITING_LANGS),
    ],
    "style": [("lang", STYLE_LANGS)],
}


def _missing_field(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        if d.parse_error:
            yield LintFinding(
                "MISSING_FIELD",
                "error",
                d.rel,
                f"frontmatter unparsable: {d.parse_error}",
                fixable=False,
            )
            continue
        for key in _REQUIRED_BY_KIND.get(d.kind, ()):
            if key not in d.fm:
                fixable = key in ("created_at", "slug")
                yield LintFinding(
                    "MISSING_FIELD",
                    "error",
                    d.rel,
                    f"required field {key!r} missing",
                    field=key,
                    fixable=fixable,
                )


def _invalid_value(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        for key, allowed in _ENUMS_BY_KIND.get(d.kind, []):
            val = d.fm.get(key)
            if val is not None and val not in allowed:
                yield LintFinding(
                    "INVALID_VALUE", "error", d.rel, f"{key}={val!r} not in {allowed}", field=key
                )


def _duplicate_slug(snap: _Snapshot) -> Iterator[LintFinding]:
    # Group: (kind, bucket-or-None) → slug → [paths]
    groups: dict[tuple[str, str | None], dict[str, list[str]]] = {}
    for d in snap.docs:
        slug = d.fm.get("slug") if d.kind != "chunk" else d.fm.get("topic")
        if not slug:
            continue
        bucket = d.fm.get("bucket") if d.kind == "wiki" else None
        key = (d.kind, bucket)
        groups.setdefault(key, {}).setdefault(slug, []).append(d.rel)
    for (_kind, _bucket), bucket_slugs in groups.items():
        for slug, paths in bucket_slugs.items():
            if len(paths) > 1:
                for p in paths:
                    yield LintFinding(
                        "DUPLICATE_SLUG",
                        "error",
                        p,
                        f"slug {slug!r} appears in {len(paths)} files: {', '.join(paths)}",
                    )


def _broken_wikilink(snap: _Snapshot) -> Iterator[LintFinding]:
    known = {d.fm.get("slug") for d in snap.docs if d.kind == "wiki" and d.fm.get("slug")}
    for d in snap.docs:
        if d.kind not in ("wiki", "writing"):
            continue
        for m in _WIKILINK_RE.findall(d.body):
            if m not in known:
                yield LintFinding(
                    "BROKEN_WIKILINK",
                    "error",
                    d.rel,
                    f"[[{m}]] doesn't resolve to any wiki slug",
                )


def _broken_derived_from(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        derived = d.fm.get("derived_from")
        if not isinstance(derived, list):
            continue
        for ref in derived:
            if not isinstance(ref, str):
                continue
            if not (root / ref).exists():
                yield LintFinding(
                    "BROKEN_DERIVED_FROM",
                    "error",
                    d.rel,
                    f"derived_from path doesn't exist: {ref}",
                )


def _orphan_promoted_source(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    captures_by_rel = {d.rel: d for d in snap.docs if d.kind == "capture"}
    for d in snap.docs:
        if d.kind != "wiki":
            continue
        pf = d.fm.get("promoted_from")
        if not pf:
            continue
        src = captures_by_rel.get(pf)
        if src is None:
            continue  # BROKEN_DERIVED_FROM-style would catch missing files separately
        if src.fm.get("status") != "archived":
            yield LintFinding(
                "ORPHAN_PROMOTED_SOURCE",
                "error",
                d.rel,
                f"promoted_from {pf} has status={src.fm.get('status')!r}, expected 'archived'",
                fixable=True,
            )


def _style_flat_file(snap: _Snapshot) -> Iterator[LintFinding]:
    """Reject markdown files outside data/style/<style>/<sample>.md (wrong nesting depth)."""
    for d in snap.docs:
        if d.kind != "style":
            continue
        # Valid path: exactly data/style/<style>/<sample>.md → 4 parts.
        parts = d.rel.split("/")
        if len(parts) != 4:
            yield LintFinding(
                "STYLE_FLAT_FILE",
                "error",
                d.rel,
                "Style samples must live in data/style/<style>/<sample>.md (wrong nesting depth).",
            )


# --------- Warnings ---------

_NOW = time.time  # indirection so tests can monkeypatch if needed


def _stale_draft(snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _STALE_DRAFT_DAYS * 86400
    for d in snap.by_kind("capture"):
        if d.fm.get("status") == "draft" and d.mtime < cutoff:
            yield LintFinding(
                "STALE_DRAFT",
                "warning",
                d.rel,
                f"draft for >{_STALE_DRAFT_DAYS} days; review or rm",
            )


def _stale_stub(snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _STALE_STUB_DAYS * 86400
    for d in snap.by_kind("wiki"):
        if d.fm.get("status") == "stub" and d.mtime < cutoff:
            yield LintFinding(
                "STALE_STUB",
                "warning",
                d.rel,
                f"stub for >{_STALE_STUB_DAYS} days; expand or deprecate",
            )


def _orphan_wiki(snap: _Snapshot) -> Iterator[LintFinding]:
    # Build incoming-link map
    incoming: dict[str, set[str]] = {}
    for d in snap.docs:
        if d.kind not in ("wiki", "writing", "capture"):
            continue
        for slug in _WIKILINK_RE.findall(d.body):
            incoming.setdefault(slug, set()).add(d.rel)
    derived_from_targets: set[str] = set()
    for d in snap.docs:
        for ref in d.fm.get("derived_from") or []:
            if isinstance(ref, str):
                derived_from_targets.add(ref)
    for d in snap.by_kind("wiki"):
        slug = d.fm.get("slug")
        if not slug:
            continue
        has_incoming = bool(incoming.get(slug))
        is_derived_target = d.rel in derived_from_targets
        has_tags = bool(d.fm.get("tags"))
        if not (has_incoming or is_derived_target or has_tags):
            yield LintFinding(
                "ORPHAN_WIKI", "warning", d.rel, "no incoming wikilinks, derived_from, or tags"
            )


def _large_chunk_never_promoted(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _LARGE_CHUNK_DAYS * 86400
    # Build set of paths referenced by any wiki page (via derived_from or wikilinks/citations)
    referenced: set[str] = set()
    for d in snap.docs:
        if d.kind != "wiki":
            continue
        for ref in d.fm.get("derived_from") or []:
            if isinstance(ref, str):
                referenced.add(ref)
        for m in _CITATION_RE.findall(d.body):
            referenced.add(m)
    for d in snap.by_kind("chunk"):
        if d.fm.get("status") != "ready":
            continue
        if d.mtime >= cutoff:
            continue
        topic_dir = d.path.parent.relative_to(root).as_posix() + "/"
        if any(r.startswith(topic_dir) for r in referenced):
            continue
        yield LintFinding(
            "LARGE_CHUNK_NEVER_PROMOTED",
            "warning",
            d.rel,
            f"chunk ready for >{_LARGE_CHUNK_DAYS} days with no wiki references; consider synthesizing.",
        )


def _lang_inconsistent(snap: _Snapshot) -> Iterator[LintFinding]:
    # Heuristic: declared lang=ko but body has zero Hangul AND >100 chars → mismatch
    # Declared lang=en but body has Hangul → mismatch
    for d in snap.docs:
        body = d.body
        if len(body) < 80:
            continue
        lang = d.fm.get("lang")
        has_hangul = bool(_HANGUL_RE.search(body))
        if lang == "ko" and not has_hangul:
            yield LintFinding(
                "LANG_INCONSISTENT",
                "warning",
                d.rel,
                "declared lang=ko but body has no Hangul characters",
            )
        elif lang == "en" and has_hangul:
            yield LintFinding(
                "LANG_INCONSISTENT",
                "warning",
                d.rel,
                "declared lang=en but body contains Hangul characters",
            )


def _raw_body_mutated(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.by_kind("capture"):
        if d.fm.get("status") != "reviewed":
            continue
        stored = d.fm.get("body_hash")
        if not stored:
            continue  # legacy / pre-M4 capture — skip silently
        actual = hashlib.sha256(d.body.encode("utf-8")).hexdigest()
        if actual != stored:
            yield LintFinding(
                "RAW_BODY_MUTATED",
                "warning",
                d.rel,
                "body changed after status=reviewed (immutability violation)",
            )


def _broken_citation(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.by_kind("wiki"):
        for ref in _CITATION_RE.findall(d.body):
            if not (root / ref).exists():
                yield LintFinding(
                    "BROKEN_CITATION", "warning", d.rel, f"citation path doesn't exist: {ref}"
                )


def _writing_grounding(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    """Surface R1/R2/R3/R4 grounding violations on writing docs as warnings.

    Mirrors the promote-time hard gate so users see issues during `pkm lint`
    instead of only at promote time.
    """
    from pkm.lint.grounding import check_grounding, load_config

    cfg = load_config(root)
    if not cfg.get("enabled", True):
        return
    for d in snap.by_kind("writing"):
        for v in check_grounding(d.fm, d.body, root, config=cfg):
            yield LintFinding(
                code=v.code,
                severity="warning",
                path=d.rel,
                message=v.message,
                fixable=False,
            )


def _missing_link_candidate(root: Path) -> Iterator[LintFinding]:
    """Surface wiki pairs that look semantically close but aren't directly
    linked. One finding per pair, attached to the alphabetically-first path so
    `pkm lint` doesn't double-report.

    Silently skips when `.pkm/index.db` is absent or feature is disabled —
    `find_suggestions` handles every fallback.
    """
    from pkm.lint.missing_links import find_suggestions

    for sug in find_suggestions(root):
        other_slug = Path(sug.dst_path).stem
        yield LintFinding(
            "MISSING_LINK_CANDIDATE",
            "warning",
            sug.src_path,
            f"semantically close to {sug.dst_path} (similarity={sug.similarity:.2f}) "
            f"but no direct link; consider [[{other_slug}]] or shared tags.",
        )


# --------- Orchestrator ---------


def collect_findings(root: Path) -> list[LintFinding]:
    """Run every rule against the root and return findings sorted by (path, code)."""
    snap = _load_snapshot(root)
    out: list[LintFinding] = []
    out.extend(_missing_field(snap))
    out.extend(_invalid_value(snap))
    out.extend(_duplicate_slug(snap))
    out.extend(_broken_wikilink(snap))
    out.extend(_broken_derived_from(root, snap))
    out.extend(_orphan_promoted_source(root, snap))
    out.extend(_style_flat_file(snap))
    out.extend(_stale_draft(snap))
    out.extend(_stale_stub(snap))
    out.extend(_orphan_wiki(snap))
    out.extend(_large_chunk_never_promoted(root, snap))
    out.extend(_lang_inconsistent(snap))
    out.extend(_raw_body_mutated(snap))
    out.extend(_broken_citation(root, snap))
    out.extend(_writing_grounding(root, snap))
    out.extend(_missing_link_candidate(root))
    out.sort(key=lambda f: (f.path, f.code))
    return out
