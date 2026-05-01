# M2 — Capture & Chunks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the first user-facing data layer — `pkm capture *` and `pkm chunks *` commands with automatic `data/log.md` append and `data/index.md` regeneration on every mutation. Wire up the `/collect`, `/research`, `/review-captures` slash command templates.

**Architecture:** Pure-Python file IO layered on M1's `pkm.store` primitives (`frontmatter`, `files`). New `pkm.store.frontmatter_schemas` validates/serializes the four schema shapes from spec §6.1; M2 only exercises *capture* and *chunk*. New `pkm.store.log` (append-only event log) and `pkm.store.toc` (index regenerator) read/write `data/log.md` and `data/index.md`. Each command lives in `pkm/commands/<name>.py` and exposes `register(app)`. All mutations call a tiny `_post_mutation(root, event)` helper that appends to log + rebuilds the TOC; this is the single chokepoint for M2's auto-update invariant.

**Tech Stack:** No new runtime deps. Heavy lifting reuses M1's `pyyaml`, `typer`, `pkm.store.files.atomic_write`, `pkm.store.frontmatter.{parse,serialize}`. Tests use the same memory-safe conftest from M1.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` (esp. §3.2 capture/chunks, §6.1 frontmatter schemas, §6.6 auto side-effects, §8 testing).

**Out-of-scope for M2 (deferred):**
- **M2.5 / M3**: git auto-commit (`pkm/store/git.py` + wrapping mutations). M2 mutations write to disk + log + index; the `git_commit` JSON field is omitted until git lands. Spec §6.6's "auto git commit" invariant is unmet at end-of-M2 by design.
- **M3**: SQLite + sqlite-vec, FTS5 indexing, embedder. M2 has no `.pkm/index.db` interaction.
- **M3+**: `pkm extract` (PDF/HTML→md) — needs `pdfplumber` + `markdownify`, big deps. Not in M2's strict deliverable list per spec §9.3 Week 2-3.
- **Future**: `pkm log show --since DATE` (filter by timestamp). Spec §3.2 lists `--since` but acceptance criteria don't require it; M2 ships only `--type` filtering. Add `--since` when a workflow needs it (likely M3 with reindex).
- **M4**: `pkm promote/demote/wiki edit`, `pkm lint`.
- **M5**: `pkm write`, AI bridge.

After M2 a developer can: `pkm init` → `pkm capture create --slug foo --status draft <<< "body"` → `pkm capture list --json` → `pkm capture set-status foo reviewed` → `pkm capture show foo`. Same for chunks. Every mutation appends a line to `data/log.md` and refreshes `data/index.md`. The Claude Code session can use `/collect <url>` to drive this end-to-end.

---

## File Structure

### Created in M2

```
pkm/store/frontmatter_schemas.py    # capture/chunk validation + defaults + serialize
pkm/store/log.py                    # append_event(root, type, payload)
pkm/store/toc.py                    # rebuild_index(root) → data/index.md
pkm/store/refs.py                   # resolve_capture_id_or_slug, resolve_chunk_topic

pkm/commands/capture.py             # `pkm capture *` — replaces no stub (capture command group is new)
pkm/commands/chunks.py              # `pkm chunks *`
pkm/commands/log.py                 # `pkm log {append,show}`
pkm/commands/index.py               # `pkm index rebuild`

pkm/_mutations.py                   # _post_mutation(root, event) — log+index chokepoint

pkm/templates/.claude/commands/collect.md          # /collect <url|text>
pkm/templates/.claude/commands/research.md         # /research <topic>
pkm/templates/.claude/commands/review-captures.md  # /review-captures

tests/test_frontmatter_schemas.py
tests/test_store_log.py
tests/test_store_toc.py
tests/test_store_refs.py
tests/test_capture.py
tests/test_chunks.py
tests/test_log_command.py
tests/test_index_command.py
tests/test_post_mutation.py
tests/fixtures/sample_pkm.py        # builds a fresh PKM scaffold in tmp_path
```

### Modified in M2

```
pkm/cli.py                          # register new command groups (capture, chunks, log, index)
pkm/commands/init.py                # add the three .claude/commands/*.md templates
pkm/commands/doctor.py              # add log.md / index.md presence checks (already in _REQUIRED_PATHS — verify)
pkm/templates/SCHEMA.md.template    # fill §3 (frontmatter capture+chunk) and §4 (capture/chunks workflows)
pkm/templates/config.toml.template  # (no change — present from M1)
README.md                           # mark M2 done at end
```

### Why these boundaries

- **`frontmatter_schemas.py`** is the single source of truth for what each schema requires/defaults. Capture and chunk live together because their validation logic is structurally identical (same key set / different keys). M3's wiki+writing schemas land in the same file.
- **`pkm/store/log.py` / `toc.py`** are pure file-level primitives. They have no knowledge of `capture` vs `chunk` — they take generic events. This keeps the auto-update chokepoint trivial.
- **`pkm/_mutations.py`** is the **only** place that strings log+index together. Every mutation in `commands/*.py` calls `_post_mutation(root, event)` and never touches `log` or `toc` directly. Single chokepoint = easy to extend in M3 (add git_commit) and M5 (add reindex).
- **Slash command templates** live under `pkm/templates/.claude/commands/`. `pkm init` already creates `.claude/commands/` directory; we now seed it with three files.
- **`refs.py`** handles "find a capture by slug or fragment" — used by `show`, `set-status`, `rm`. Centralizing it avoids each command re-implementing path search.

---

## Task list (executor checklist)

10 tasks. Tasks 1–8 use TDD. Task 9 is wiring + templates. Task 10 is verification.

> **For each task, work in the order listed and run the exact commands shown.** Commit after every task with the suggested message.

---

### Task 1: Frontmatter schemas — capture & chunk (TDD)

**Files:**
- Create: `pkm/store/frontmatter_schemas.py`
- Test: `tests/test_frontmatter_schemas.py`

Captures and chunks both have a fixed set of required + optional fields. We need `validate(kind, fm)` (raises `PKMValidationError`) and `defaults(kind, **overrides)` (returns a dict suitable for `frontmatter.serialize`).

#### Steps

- [ ] **Step 1.1: Write failing tests `tests/test_frontmatter_schemas.py`**

```python
"""Tests for pkm.store.frontmatter_schemas."""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import (
    capture_defaults,
    chunk_defaults,
    validate_capture,
    validate_chunk,
)


# --- capture ----

def test_capture_defaults_minimal():
    fm = capture_defaults(slug="2026-05-01-foo", title="foo")
    assert fm["slug"] == "2026-05-01-foo"
    assert fm["title"] == "foo"
    assert fm["status"] == "draft"
    assert fm["lang"] == "ko"
    assert fm["source_type"] == "text"
    # ISO 8601 with timezone
    assert "T" in fm["created_at"]
    datetime.fromisoformat(fm["created_at"])  # parseable


def test_capture_defaults_with_url():
    fm = capture_defaults(slug="x", title="t", source_url="https://x")
    assert fm["source_type"] == "url"
    assert fm["source_url"] == "https://x"
    assert "fetched_at" in fm


def test_capture_validate_ok():
    fm = capture_defaults(slug="x", title="t")
    validate_capture(fm)  # no exception


def test_capture_validate_missing_required_raises():
    with pytest.raises(PKMValidationError, match="missing required"):
        validate_capture({"slug": "x"})  # title, status, lang, source_type, created_at missing


def test_capture_validate_status_enum():
    fm = capture_defaults(slug="x", title="t")
    fm["status"] = "weird"
    with pytest.raises(PKMValidationError, match="status"):
        validate_capture(fm)


def test_capture_validate_lang_enum():
    fm = capture_defaults(slug="x", title="t")
    fm["lang"] = "fr"
    with pytest.raises(PKMValidationError, match="lang"):
        validate_capture(fm)


# --- chunk ----

def test_chunk_defaults_minimal():
    fm = chunk_defaults(topic="oauth-deep-dive")
    assert fm["topic"] == "oauth-deep-dive"
    assert fm["status"] == "collecting"
    assert fm["lang"] == "mixed"
    assert fm["sources"] == []


def test_chunk_validate_ok():
    fm = chunk_defaults(topic="t")
    validate_chunk(fm)


def test_chunk_validate_missing_topic_raises():
    with pytest.raises(PKMValidationError, match="topic"):
        validate_chunk({"status": "collecting", "lang": "ko", "created_at": "x", "sources": []})


def test_chunk_validate_status_enum():
    fm = chunk_defaults(topic="t")
    fm["status"] = "wat"
    with pytest.raises(PKMValidationError, match="status"):
        validate_chunk(fm)
```

- [ ] **Step 1.2: Run tests — must fail (no module)**

```bash
.venv/bin/pytest tests/test_frontmatter_schemas.py -v
```

- [ ] **Step 1.3: Write `pkm/store/frontmatter_schemas.py`**

```python
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
```

- [ ] **Step 1.4: Run tests — must pass (10 passed)**

- [ ] **Step 1.5: Commit**

```bash
git add pkm/store/frontmatter_schemas.py tests/test_frontmatter_schemas.py
git commit -m "M2.1: capture & chunk frontmatter schemas + validation"
```

---

### Task 2: log.md primitive (TDD)

**Files:**
- Create: `pkm/store/log.py`
- Test: `tests/test_store_log.py`

`log.md` is an append-only event log (spec §2). Each line is a single event. Format chosen: one Markdown table row per event, ISO 8601 timestamp + type + slug + free-form message. Why a table? Cheap to grep, render-friendly in Obsidian, machine-parseable. We append; we never rewrite.

#### Steps

- [ ] **Step 2.1: Write failing tests `tests/test_store_log.py`**

```python
"""Tests for pkm.store.log."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.store.log import LogEvent, append_event, read_events


def test_append_event_creates_log_with_header(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="2026-05-01-foo", message="hi"))
    log = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # Header lines
    assert log.startswith("# Log\n")
    assert "| timestamp | type | ref | message |" in log
    assert "| --- |" in log
    # Event row present
    assert "capture.create" in log
    assert "2026-05-01-foo" in log
    assert "hi" in log


def test_append_event_appends_to_existing(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="a", message=""))
    append_event(tmp_path, LogEvent(type="capture.create", ref="b", message=""))
    rows = (tmp_path / "data" / "log.md").read_text(encoding="utf-8").splitlines()
    data_rows = [r for r in rows if r.startswith("| 2") or r.startswith("| 1")]
    # Two timestamped event rows
    assert len(data_rows) == 2


def test_append_event_pipe_in_message_is_escaped(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="x", message="a | b"))
    log = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # The pipe in the message must not break the table — escape as \|
    assert r"a \| b" in log


def test_read_events_returns_chronological(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="t1", ref="r1", message="m1"))
    append_event(tmp_path, LogEvent(type="t2", ref="r2", message="m2"))
    events = read_events(tmp_path)
    assert [e.type for e in events] == ["t1", "t2"]
    assert [e.ref for e in events] == ["r1", "r2"]


def test_read_events_filters_by_type(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="a", message=""))
    append_event(tmp_path, LogEvent(type="chunks.new", ref="b", message=""))
    events = read_events(tmp_path, type_filter="capture.create")
    assert [e.ref for e in events] == ["a"]


def test_read_events_on_missing_log(tmp_path: Path):
    """No log.md → no events, no error."""
    assert read_events(tmp_path) == []
```

- [ ] **Step 2.2: Run tests — must fail**

- [ ] **Step 2.3: Write `pkm/store/log.py`**

```python
"""Append-only event log (`data/log.md`).

Format: a single Markdown table. Header is written once; each subsequent
mutation appends one row. Pipes in user-supplied text are escaped as `\\|`
so the table never breaks.

Spec reference: §2 (layout — log.md), §6.6 (auto-update).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_LOG_REL = "data/log.md"
_HEADER = (
    "# Log\n\n"
    "_Append-only event log. Do not edit by hand._\n\n"
    "| timestamp | type | ref | message |\n"
    "| --- | --- | --- | --- |\n"
)


@dataclass
class LogEvent:
    type: str
    ref: str
    message: str = ""
    timestamp: str | None = None


def _escape(s: str) -> str:
    return s.replace("|", r"\|").replace("\n", " ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append_event(root: Path, event: LogEvent) -> None:
    """Append a single row to `data/log.md`. Creates the file with header
    if missing or empty."""
    log_path = root / _LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = event.timestamp or _now_iso()
    row = f"| {ts} | {_escape(event.type)} | {_escape(event.ref)} | {_escape(event.message)} |\n"
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text(_HEADER + row, encoding="utf-8")
        return
    with log_path.open("a", encoding="utf-8") as f:
        f.write(row)


def read_events(root: Path, *, type_filter: str | None = None) -> list[LogEvent]:
    """Read all events from log.md. Returns empty list if file missing."""
    log_path = root / _LOG_REL
    if not log_path.exists():
        return []
    out: list[LogEvent] = []
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        # Only data rows (start with "| " and don't match header / separator)
        if not raw.startswith("| "):
            continue
        if raw.startswith("| timestamp") or raw.startswith("| ---"):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        ts, typ, ref, msg = cells
        # Unescape \|
        typ = typ.replace(r"\|", "|")
        ref = ref.replace(r"\|", "|")
        msg = msg.replace(r"\|", "|")
        if type_filter and typ != type_filter:
            continue
        out.append(LogEvent(type=typ, ref=ref, message=msg, timestamp=ts))
    return out
```

- [ ] **Step 2.4: Run tests — must pass (6 passed)**

- [ ] **Step 2.5: Commit**

```bash
git add pkm/store/log.py tests/test_store_log.py
git commit -m "M2.2: data/log.md primitive — append-only event log"
```

---

### Task 3: index.md TOC primitive (TDD)

**Files:**
- Create: `pkm/store/toc.py`
- Test: `tests/test_store_toc.py`

`data/index.md` is the auto-generated TOC. It is **regenerated** every mutation; it is never appended to. Content: per-bucket sections listing each file (or chunk topic) with its title/slug and status.

Note: M2 only knows about `raw/captures/*.md` and `raw/chunks/*/README.md`. `wiki/` and `writing/` sections are stubs ("(empty until Mn)") so the document is structurally complete.

#### Steps

- [ ] **Step 3.1: Write failing tests `tests/test_store_toc.py`**

```python
"""Tests for pkm.store.toc."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.store.frontmatter import serialize
from pkm.store.toc import rebuild_index


def _make_pkm(root: Path) -> None:
    """Minimal PKM scaffold (mirrors `pkm init`)."""
    for d in [
        "data/raw/captures",
        "data/raw/chunks",
        "data/wiki/concepts",
        "data/writing",
    ]:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "data/index.md").write_text("# Index\n", encoding="utf-8")


def _write_capture(root: Path, slug: str, title: str, status: str = "draft") -> None:
    fm = {"slug": slug, "title": title, "status": status, "lang": "ko"}
    (root / "data/raw/captures" / f"{slug}.md").write_text(
        serialize(fm, f"body of {slug}"), encoding="utf-8"
    )


def test_rebuild_index_empty(tmp_path: Path):
    _make_pkm(tmp_path)
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert text.startswith("# Index")
    assert "## Captures" in text
    assert "## Chunks" in text
    # Empty bucket marker
    assert "_(none)_" in text


def test_rebuild_index_with_captures(tmp_path: Path):
    _make_pkm(tmp_path)
    _write_capture(tmp_path, "2026-05-01-foo", "Foo", "draft")
    _write_capture(tmp_path, "2026-05-02-bar", "Bar", "reviewed")
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    # Both slugs listed under Captures
    cap_section = text.split("## Captures")[1].split("## ")[0]
    assert "2026-05-01-foo" in cap_section
    assert "2026-05-02-bar" in cap_section
    # Status visible
    assert "draft" in cap_section
    assert "reviewed" in cap_section


def test_rebuild_index_with_chunks(tmp_path: Path):
    _make_pkm(tmp_path)
    topic_dir = tmp_path / "data/raw/chunks/oauth"
    topic_dir.mkdir()
    fm = {"topic": "oauth", "status": "collecting", "lang": "ko", "sources": []}
    (topic_dir / "README.md").write_text(serialize(fm, "desc"), encoding="utf-8")
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    chunks_section = text.split("## Chunks")[1].split("## ")[0]
    assert "oauth" in chunks_section
    assert "collecting" in chunks_section


def test_rebuild_index_skips_files_without_frontmatter(tmp_path: Path):
    _make_pkm(tmp_path)
    (tmp_path / "data/raw/captures/no-fm.md").write_text("just body", encoding="utf-8")
    rebuild_index(tmp_path)  # no exception
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    # File without frontmatter is listed by filename with status "?"
    assert "no-fm" in text


def test_rebuild_index_is_idempotent(tmp_path: Path):
    _make_pkm(tmp_path)
    _write_capture(tmp_path, "x", "X")
    rebuild_index(tmp_path)
    first = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    rebuild_index(tmp_path)
    second = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert first == second
```

- [ ] **Step 3.2: Run tests — must fail**

- [ ] **Step 3.3: Write `pkm/store/toc.py`**

```python
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
```

- [ ] **Step 3.4: Run tests — must pass (5 passed)**

- [ ] **Step 3.5: Commit**

```bash
git add pkm/store/toc.py tests/test_store_toc.py
git commit -m "M2.3: data/index.md TOC regeneration primitive"
```

---

### Task 4: refs.py + post_mutation chokepoint (TDD)

**Files:**
- Create: `pkm/store/refs.py`
- Create: `pkm/_mutations.py`
- Test: `tests/test_store_refs.py`
- Test: `tests/test_post_mutation.py`

`refs.py` resolves a user-supplied `<id-or-slug>` to a concrete `Path`. Captures use slug equality first, then "slug contains" as a fallback (substring match) — this is what the spec implies by "id-or-slug". Ambiguous matches (>1) raise `PKMValidationError`.

`_mutations.py` is the chokepoint helper: every mutation calls `_post_mutation(root, event)` to atomically update log + index.

#### Steps

- [ ] **Step 4.1: Write failing tests**

`tests/test_store_refs.py`:
```python
"""Tests for pkm.store.refs."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store.refs import resolve_capture, resolve_chunk_topic


def _mkcapture(root: Path, slug: str) -> Path:
    p = root / "data/raw/captures" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nslug: {slug}\n---\nbody", encoding="utf-8")
    return p


def test_resolve_capture_exact_slug(tmp_path: Path):
    p = _mkcapture(tmp_path, "2026-05-01-foo")
    assert resolve_capture(tmp_path, "2026-05-01-foo") == p


def test_resolve_capture_substring(tmp_path: Path):
    p = _mkcapture(tmp_path, "2026-05-01-foo-bar")
    assert resolve_capture(tmp_path, "foo-bar") == p


def test_resolve_capture_ambiguous_raises(tmp_path: Path):
    _mkcapture(tmp_path, "2026-05-01-x")
    _mkcapture(tmp_path, "2026-05-02-x")
    with pytest.raises(PKMValidationError, match="ambiguous"):
        resolve_capture(tmp_path, "x")


def test_resolve_capture_not_found(tmp_path: Path):
    (tmp_path / "data/raw/captures").mkdir(parents=True)
    with pytest.raises(PKMNotFoundError):
        resolve_capture(tmp_path, "nope")


def test_resolve_chunk_topic(tmp_path: Path):
    topic_dir = tmp_path / "data/raw/chunks/oauth"
    topic_dir.mkdir(parents=True)
    (topic_dir / "README.md").write_text("---\ntopic: oauth\n---\n", encoding="utf-8")
    assert resolve_chunk_topic(tmp_path, "oauth") == topic_dir


def test_resolve_chunk_topic_not_found(tmp_path: Path):
    (tmp_path / "data/raw/chunks").mkdir(parents=True)
    with pytest.raises(PKMNotFoundError):
        resolve_chunk_topic(tmp_path, "absent")
```

`tests/test_post_mutation.py`:
```python
"""Tests for pkm._mutations._post_mutation."""
from __future__ import annotations
from pathlib import Path

from pkm._mutations import post_mutation
from pkm.store.log import LogEvent, read_events


def _make_pkm(root: Path) -> None:
    for d in ["data/raw/captures", "data/raw/chunks", "data/wiki/concepts", "data/writing"]:
        (root / d).mkdir(parents=True, exist_ok=True)


def test_post_mutation_appends_log_and_rebuilds_index(tmp_path: Path):
    _make_pkm(tmp_path)
    post_mutation(tmp_path, LogEvent(type="capture.create", ref="x", message=""))

    events = read_events(tmp_path)
    assert len(events) == 1
    assert events[0].type == "capture.create"

    idx = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert "## Captures" in idx
```

- [ ] **Step 4.2: Run tests — must fail**

- [ ] **Step 4.3: Write `pkm/store/refs.py`**

```python
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
```

- [ ] **Step 4.4: Write `pkm/_mutations.py`**

```python
"""Single chokepoint for the auto side-effects every mutation must trigger.

In M2: append-to-log + rebuild-index.
In M3: + git auto-commit.
In M5: + targeted reindex.

Every command in `pkm.commands.*` that changes the filesystem MUST end with
`post_mutation(root, event)` rather than calling log/toc directly. This keeps
the side-effect surface visible in one place.
"""
from __future__ import annotations

from pathlib import Path

from pkm.store.log import LogEvent, append_event
from pkm.store.toc import rebuild_index


def post_mutation(root: Path, event: LogEvent) -> None:
    """Append the event to log.md and regenerate index.md."""
    append_event(root, event)
    rebuild_index(root)
```

- [ ] **Step 4.5: Run tests — must pass (7 passed)**

- [ ] **Step 4.6: Commit**

```bash
git add pkm/store/refs.py pkm/_mutations.py tests/test_store_refs.py tests/test_post_mutation.py
git commit -m "M2.4: ref resolver + post_mutation chokepoint"
```

---

### Task 5: `pkm capture create` (TDD)

**Files:**
- Create: `pkm/commands/capture.py` (with `create` subcommand only — list/show/etc. land in tasks 6–7)
- Test: `tests/test_capture.py`
- Modify: `pkm/cli.py` (register capture group)

`pkm capture create` accepts:
- `--slug SLUG` (required) — user-supplied stem (no date prefix; we add it)
- `--title TITLE` (required) — frontmatter title
- `--url URL` (optional)
- `--from-file PATH` (optional) — body source; if absent, body comes from stdin
- `--status {draft,reviewed}` (default: draft)
- `--lang {ko,en,mixed}` (default: ko)
- `--root PATH` (default: ".")
- `--json` (optional)

Final on-disk slug is `<YYYY-MM-DD>-<slugify(slug)>`. Body is written verbatim. Refuses to overwrite existing capture (no `--force` in M2).

#### Steps

- [ ] **Step 5.1: Write failing tests `tests/test_capture.py`** (just the create subset)

```python
"""Tests for pkm.commands.capture (M2.5: create subcommand)."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_create_from_stdin(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "foo", "--title", "Foo"],
        input="body here\n",
    )
    assert res.exit_code == 0, res.output
    # Find the created file (date-prefixed slug)
    created = list((tmp_path / "data/raw/captures").glob("*-foo.md"))
    assert len(created) == 1
    fm, body = parse(created[0].read_text(encoding="utf-8"))
    assert fm["title"] == "Foo"
    assert fm["status"] == "draft"
    assert fm["source_type"] == "text"
    assert body == "body here\n"


def test_create_with_url_and_status(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "bar", "--title", "Bar",
         "--url", "https://x", "--status", "reviewed"],
        input="ignored",
    )
    assert res.exit_code == 0, res.output
    p = next((tmp_path / "data/raw/captures").glob("*-bar.md"))
    fm, _ = parse(p.read_text(encoding="utf-8"))
    assert fm["source_url"] == "https://x"
    assert fm["source_type"] == "url"
    assert fm["status"] == "reviewed"


def test_create_from_file(tmp_path: Path):
    _init(tmp_path)
    src = tmp_path / "in.md"
    src.write_text("from-file body", encoding="utf-8")
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "qux", "--title", "Qux", "--from-file", str(src)],
    )
    assert res.exit_code == 0
    p = next((tmp_path / "data/raw/captures").glob("*-qux.md"))
    _, body = parse(p.read_text(encoding="utf-8"))
    assert body == "from-file body"


def test_create_json_output(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "baz", "--title", "Baz", "--json"],
        input="b",
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["id"].endswith("-baz")
    assert "raw/captures" in payload["path"]


def test_create_appends_log_and_rebuilds_index(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "logme", "--title", "Logme"],
        input="b",
    )
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "capture.create" in log
    assert "logme" in log
    idx = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert "logme" in idx


def test_create_invalid_status_clean_error(tmp_path: Path):
    """Bad enum must surface as VALIDATION_ERROR, not a Python traceback."""
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "x", "--title", "X", "--status", "weird"],
        input="b",
    )
    assert res.exit_code != 0
    assert "VALIDATION_ERROR" in res.output or "status" in res.output.lower()


def test_create_refuses_existing_slug(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["capture", "create", "--root", str(tmp_path),
                        "--slug", "dup", "--title", "Dup"], input="x")
    res2 = runner.invoke(app, ["capture", "create", "--root", str(tmp_path),
                               "--slug", "dup", "--title", "Dup2"], input="y")
    assert res2.exit_code != 0
    assert "exists" in res2.output.lower() or "STATE_ERROR" in res2.output
```

- [ ] **Step 5.2: Write `pkm/commands/capture.py` (create only)**

```python
"""`pkm capture *` — captures (raw/captures/).

Spec reference: §3.2 (commands), §6.1 (capture frontmatter), §6.6 (auto log/index).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMStateError
from pkm.store.files import atomic_write, date_prefix_slug
from pkm.store.frontmatter import serialize
from pkm.store.frontmatter_schemas import capture_defaults, validate_capture
from pkm.store.log import LogEvent


def _capture_path(root: Path, full_slug: str) -> Path:
    return root / "data" / "raw" / "captures" / f"{full_slug}.md"


def _read_body(from_file: Path | None) -> str:
    if from_file is not None:
        return from_file.read_text(encoding="utf-8")
    return sys.stdin.read()


def _do_create(
    root: Path,
    *,
    slug: str,
    title: str,
    url: str | None,
    from_file: Path | None,
    status: str,
    lang: str,
) -> dict:
    full_slug = date_prefix_slug(slug)
    target = _capture_path(root, full_slug)
    if target.exists():
        raise PKMStateError(
            f"capture {full_slug} already exists at {target.relative_to(root)}",
            hint="Pick a different slug or remove the existing capture.",
        )
    body = _read_body(from_file)
    fm = capture_defaults(slug=full_slug, title=title, source_url=url, status=status, lang=lang)
    validate_capture(fm)
    atomic_write(target, serialize(fm, body))
    post_mutation(root, LogEvent(type="capture.create", ref=full_slug, message=title))
    return {
        "ok": True,
        "id": full_slug,
        "path": target.relative_to(root).as_posix(),
    }


def register(app: typer.Typer) -> None:
    capture_app = typer.Typer(name="capture", help="Manage captures (raw/captures/).", no_args_is_help=True)
    app.add_typer(capture_app, name="capture")

    @capture_app.command("create")
    def create_cmd(
        slug: str = typer.Option(..., "--slug", help="Stem for the capture filename (date prefix added automatically)."),
        title: str = typer.Option(..., "--title", help="Capture title."),
        url: str | None = typer.Option(None, "--url", help="Source URL."),
        from_file: Path | None = typer.Option(None, "--from-file", help="Read body from this file (else stdin)."),
        status: str = typer.Option("draft", "--status", help="draft | reviewed"),
        lang: str = typer.Option("ko", "--lang", help="ko | en | mixed"),
        root: Path = typer.Option(Path("."), "--root", "-r", help="PKM root."),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON summary."),
    ) -> None:
        """Create a new capture under data/raw/captures/."""
        try:
            result = _do_create(
                root, slug=slug, title=title, url=url, from_file=from_file,
                status=status, lang=lang,
            )
        except PKMError as e:  # PKMStateError (existing) | PKMValidationError (bad enum)
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None

        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"Created capture: {result['path']}")
```

- [ ] **Step 5.3: Modify `pkm/cli.py` to register capture group**

In `_register_all()`, add:
```python
from pkm.commands import capture as capture_cmd
capture_cmd.register(app)
```
(Place after `doctor_cmd.register(app)`.)

- [ ] **Step 5.4: Run tests — should pass (6 passed)**

- [ ] **Step 5.5: Commit**

```bash
git add pkm/commands/capture.py pkm/cli.py tests/test_capture.py
git commit -m "M2.5: pkm capture create — write capture + auto log/index"
```

---

### Task 6: `pkm capture list / show / set-status / rm` (TDD)

**Files:**
- Modify: `pkm/commands/capture.py` (add 4 subcommands)
- Modify: `tests/test_capture.py` (append test cases)

#### Steps

- [ ] **Step 6.1: Append tests to `tests/test_capture.py`**

```python
def _create(tmp_path, slug, title="t", status="draft", lang="ko", url=None):
    args = ["capture", "create", "--root", str(tmp_path),
            "--slug", slug, "--title", title, "--status", status, "--lang", lang]
    if url:
        args += ["--url", url]
    return runner.invoke(app, args, input="body")


def test_list_returns_all(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a")
    _create(tmp_path, "b", status="reviewed")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    slugs = [it["slug"] for it in payload["items"]]
    assert any(s.endswith("-a") for s in slugs)
    assert any(s.endswith("-b") for s in slugs)


def test_list_filter_status(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a", status="draft")
    _create(tmp_path, "b", status="reviewed")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path),
                              "--status", "reviewed", "--json"])
    payload = json.loads(res.output)
    assert all(it["status"] == "reviewed" for it in payload["items"])
    assert any(it["slug"].endswith("-b") for it in payload["items"])


def test_list_filter_lang(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a", lang="ko")
    _create(tmp_path, "b", lang="en")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path),
                              "--lang", "en", "--json"])
    payload = json.loads(res.output)
    assert all(it["lang"] == "en" for it in payload["items"])


def test_show_by_full_slug(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "uniq", title="Uniq")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path), "--json"])
    full = json.loads(res.output)["items"][0]["slug"]
    res2 = runner.invoke(app, ["capture", "show", full, "--root", str(tmp_path), "--json"])
    assert res2.exit_code == 0
    payload = json.loads(res2.output)
    assert payload["ok"] is True
    assert payload["frontmatter"]["title"] == "Uniq"


def test_show_by_partial_slug(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "uniq")
    res = runner.invoke(app, ["capture", "show", "uniq", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0


def test_show_not_found(tmp_path):
    _init(tmp_path)
    res = runner.invoke(app, ["capture", "show", "absent", "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_set_status_changes_frontmatter(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "promoteme", status="draft")
    res = runner.invoke(app, ["capture", "set-status", "promoteme", "reviewed",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    res2 = runner.invoke(app, ["capture", "show", "promoteme",
                               "--root", str(tmp_path), "--json"])
    assert json.loads(res2.output)["frontmatter"]["status"] == "reviewed"


def test_set_status_invalid_enum(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "x")
    res = runner.invoke(app, ["capture", "set-status", "x", "weird",
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_rm_deletes_file_and_logs(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "rmme")
    res = runner.invoke(app, ["capture", "rm", "rmme", "--root", str(tmp_path)])
    assert res.exit_code == 0
    assert not list((tmp_path / "data/raw/captures").glob("*-rmme.md"))
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "capture.rm" in log
```

- [ ] **Step 6.2: Run tests — must fail**

- [ ] **Step 6.3: Extend `pkm/commands/capture.py`**

Add these functions before `register(...)`:

```python
def _list_captures(root: Path) -> list[dict]:
    cap_dir = root / "data" / "raw" / "captures"
    if not cap_dir.exists():
        return []
    out: list[dict] = []
    for p in sorted(cap_dir.glob("*.md")):
        try:
            from pkm.store.frontmatter import parse
            fm, _ = parse(p.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
        out.append({
            "slug": fm.get("slug") or p.stem,
            "title": fm.get("title") or "",
            "status": fm.get("status") or "?",
            "lang": fm.get("lang") or "?",
            "path": p.relative_to(root).as_posix(),
        })
    return out


def _do_show(root: Path, ref: str) -> dict:
    from pkm.store.frontmatter import parse
    from pkm.store.refs import resolve_capture
    p = resolve_capture(root, ref)
    fm, body = parse(p.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "slug": fm.get("slug") or p.stem,
        "path": p.relative_to(root).as_posix(),
        "frontmatter": fm,
        "body": body,
    }


def _do_set_status(root: Path, ref: str, status: str) -> dict:
    from pkm.store.frontmatter import parse
    from pkm.store.refs import resolve_capture
    p = resolve_capture(root, ref)
    fm, body = parse(p.read_text(encoding="utf-8"))
    fm["status"] = status
    validate_capture(fm)  # raises PKMValidationError on bad enum
    atomic_write(p, serialize(fm, body))
    post_mutation(root, LogEvent(type="capture.set-status", ref=fm["slug"], message=status))
    return {"ok": True, "id": fm["slug"], "path": p.relative_to(root).as_posix()}


def _do_rm(root: Path, ref: str) -> dict:
    from pkm.store.refs import resolve_capture
    p = resolve_capture(root, ref)
    slug = p.stem
    p.unlink()
    post_mutation(root, LogEvent(type="capture.rm", ref=slug, message=""))
    return {"ok": True, "id": slug, "path": p.relative_to(root).as_posix()}
```

Then inside `register(app)` add the four subcommands (paste below `create_cmd`):

```python
    @capture_app.command("list")
    def list_cmd(
        status: str | None = typer.Option(None, "--status"),
        lang: str | None = typer.Option(None, "--lang"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        items = _list_captures(root)
        if status:
            items = [it for it in items if it["status"] == status]
        if lang:
            items = [it for it in items if it["lang"] == lang]
        if json_out:
            typer.echo(json.dumps({"ok": True, "items": items}, ensure_ascii=False))
        else:
            for it in items:
                typer.echo(f"{it['slug']}  [{it['status']}/{it['lang']}]  {it['title']}")

    @capture_app.command("show")
    def show_cmd(
        ref: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        from pkm.errors import PKMError
        try:
            result = _do_show(root, ref)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"--- {result['slug']} ---")
            for k, v in result["frontmatter"].items():
                typer.echo(f"{k}: {v}")
            typer.echo("")
            typer.echo(result["body"])

    @capture_app.command("set-status")
    def set_status_cmd(
        ref: str = typer.Argument(...),
        status: str = typer.Argument(..., help="draft | reviewed | archived"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        from pkm.errors import PKMError
        try:
            result = _do_set_status(root, ref, status)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"{result['id']}: status → {status}")

    @capture_app.command("rm")
    def rm_cmd(
        ref: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        from pkm.errors import PKMError
        try:
            result = _do_rm(root, ref)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"removed {result['id']}")
```

- [ ] **Step 6.4: Run tests — must pass (full capture suite ~14 passed)**

- [ ] **Step 6.5: Commit**

```bash
git add pkm/commands/capture.py tests/test_capture.py
git commit -m "M2.6: pkm capture list/show/set-status/rm"
```

---

### Task 7: `pkm chunks *` (TDD)

**Files:**
- Create: `pkm/commands/chunks.py`
- Test: `tests/test_chunks.py`
- Modify: `pkm/cli.py` (register chunks group)

Subcommands: `new`, `add`, `list`, `show`, `set-status`, `rm`. Each follows the same shape as the capture analogues.

`pkm chunks new <topic>` creates `data/raw/chunks/<slugify(topic)>/README.md` with chunk frontmatter (`status: collecting`).

`pkm chunks add <topic> <file>...` copies each file into the topic dir. Refuses if topic missing. Adds each filename to the README's `sources:` list.

`pkm chunks rm <topic>` removes the entire topic directory tree.

#### Steps

- [ ] **Step 7.1: Write failing tests `tests/test_chunks.py`**

```python
"""Tests for pkm.commands.chunks."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_new_creates_topic_with_readme(tmp_path):
    _init(tmp_path)
    res = runner.invoke(app, ["chunks", "new", "oauth-deep-dive",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    readme = tmp_path / "data/raw/chunks/oauth-deep-dive/README.md"
    assert readme.exists()
    fm, _ = parse(readme.read_text(encoding="utf-8"))
    assert fm["topic"] == "oauth-deep-dive"
    assert fm["status"] == "collecting"


def test_new_with_description(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x",
                        "--description", "deep dive on x",
                        "--root", str(tmp_path)])
    fm, _ = parse((tmp_path / "data/raw/chunks/x/README.md").read_text(encoding="utf-8"))
    assert fm["description"] == "deep dive on x"


def test_new_refuses_existing(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "dup", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "new", "dup", "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_add_copies_file_and_records_source(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "t", "--root", str(tmp_path)])
    src = tmp_path / "src.md"
    src.write_text("source content", encoding="utf-8")
    res = runner.invoke(app, ["chunks", "add", "t", str(src),
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    copied = tmp_path / "data/raw/chunks/t/src.md"
    assert copied.read_text(encoding="utf-8") == "source content"
    fm, _ = parse((tmp_path / "data/raw/chunks/t/README.md").read_text(encoding="utf-8"))
    assert "src.md" in fm["sources"]


def test_add_multiple_files(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "t", "--root", str(tmp_path)])
    a = tmp_path / "a.md"; a.write_text("a")
    b = tmp_path / "b.md"; b.write_text("b")
    res = runner.invoke(app, ["chunks", "add", "t", str(a), str(b),
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    fm, _ = parse((tmp_path / "data/raw/chunks/t/README.md").read_text(encoding="utf-8"))
    assert "a.md" in fm["sources"] and "b.md" in fm["sources"]


def test_add_refuses_missing_topic(tmp_path):
    _init(tmp_path)
    src = tmp_path / "x.md"; src.write_text("x")
    res = runner.invoke(app, ["chunks", "add", "absent", str(src),
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_list_returns_topics(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "a", "--root", str(tmp_path)])
    runner.invoke(app, ["chunks", "new", "b", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "list", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    topics = [it["topic"] for it in payload["items"]]
    assert set(topics) >= {"a", "b"}


def test_show_returns_readme_and_files(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    src = tmp_path / "f.md"; src.write_text("y")
    runner.invoke(app, ["chunks", "add", "x", str(src), "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "show", "x", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["topic"] == "x"
    assert any(p.endswith("f.md") for p in payload["files"])


def test_set_status_changes_state(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "set-status", "x", "ready",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    fm, _ = parse((tmp_path / "data/raw/chunks/x/README.md").read_text(encoding="utf-8"))
    assert fm["status"] == "ready"


def test_set_status_invalid_enum(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "set-status", "x", "wat",
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_rm_removes_topic_tree(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "rm", "--root", str(tmp_path)])
    src = tmp_path / "f.md"; src.write_text("y")
    runner.invoke(app, ["chunks", "add", "rm", str(src), "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "rm", "rm", "--root", str(tmp_path)])
    assert res.exit_code == 0
    assert not (tmp_path / "data/raw/chunks/rm").exists()
```

- [ ] **Step 7.2: Run tests — must fail**

- [ ] **Step 7.3: Write `pkm/commands/chunks.py`**

```python
"""`pkm chunks *` — curated topic folders (raw/chunks/).

Spec reference: §3.2 (chunks commands), §6.1 (chunk frontmatter).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMNotFoundError, PKMStateError
from pkm.store.files import atomic_write, slugify
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import chunk_defaults, validate_chunk
from pkm.store.log import LogEvent
from pkm.store.refs import resolve_chunk_topic


def _topic_dir(root: Path, topic: str) -> Path:
    return root / "data" / "raw" / "chunks" / topic


def _readme(topic_dir: Path) -> Path:
    return topic_dir / "README.md"


def _do_new(root: Path, topic_in: str, description: str | None) -> dict:
    topic = slugify(topic_in)
    target = _topic_dir(root, topic)
    if target.exists():
        raise PKMStateError(
            f"chunk topic {topic!r} already exists at {target.relative_to(root)}",
            hint="Pick a different topic name or remove the existing topic.",
        )
    target.mkdir(parents=True)
    fm = chunk_defaults(topic=topic, description=description)
    validate_chunk(fm)
    atomic_write(_readme(target), serialize(fm, "(curated chunk — add sources via `pkm chunks add`)\n"))
    post_mutation(root, LogEvent(type="chunks.new", ref=topic, message=description or ""))
    return {"ok": True, "id": topic, "path": target.relative_to(root).as_posix()}


def _do_add(root: Path, topic: str, files: list[Path]) -> dict:
    target_dir = resolve_chunk_topic(root, topic)
    readme = _readme(target_dir)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    sources = list(fm.get("sources") or [])
    copied: list[str] = []
    for f in files:
        if not f.exists():
            raise PKMNotFoundError(f"file not found: {f}")
        dst = target_dir / f.name
        shutil.copy2(f, dst)
        copied.append(f.name)
        if f.name not in sources:
            sources.append(f.name)
    fm["sources"] = sources
    validate_chunk(fm)
    atomic_write(readme, serialize(fm, body))
    post_mutation(root, LogEvent(type="chunks.add", ref=topic, message=", ".join(copied)))
    return {"ok": True, "id": topic, "added": copied}


def _do_list(root: Path) -> list[dict]:
    base = root / "data" / "raw" / "chunks"
    if not base.exists():
        return []
    out: list[dict] = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        readme = _readme(d)
        fm: dict = {}
        if readme.exists():
            try:
                fm, _ = parse(readme.read_text(encoding="utf-8"))
            except Exception:
                fm = {}
        out.append({
            "topic": fm.get("topic") or d.name,
            "status": fm.get("status") or "?",
            "lang": fm.get("lang") or "?",
            "path": d.relative_to(root).as_posix(),
        })
    return out


def _do_show(root: Path, topic: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    readme = _readme(target)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    files = sorted(p.name for p in target.iterdir() if p.is_file() and p.name != "README.md")
    return {
        "ok": True,
        "topic": fm.get("topic") or target.name,
        "path": target.relative_to(root).as_posix(),
        "frontmatter": fm,
        "body": body,
        "files": files,
    }


def _do_set_status(root: Path, topic: str, status: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    readme = _readme(target)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    fm["status"] = status
    validate_chunk(fm)
    atomic_write(readme, serialize(fm, body))
    post_mutation(root, LogEvent(type="chunks.set-status", ref=topic, message=status))
    return {"ok": True, "id": topic, "status": status}


def _do_rm(root: Path, topic: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    shutil.rmtree(target)
    post_mutation(root, LogEvent(type="chunks.rm", ref=topic, message=""))
    return {"ok": True, "id": topic}


def _emit_or_raise(json_out: bool, exc: PKMError) -> None:
    if json_out:
        typer.echo(json.dumps({"ok": False, "error": exc.to_dict()}, ensure_ascii=False))
    else:
        typer.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        if exc.hint:
            typer.echo(f"  hint: {exc.hint}", err=True)
    raise typer.Exit(code=1) from None


def register(app: typer.Typer) -> None:
    chunks_app = typer.Typer(name="chunks", help="Manage chunks (raw/chunks/).", no_args_is_help=True)
    app.add_typer(chunks_app, name="chunks")

    @chunks_app.command("new")
    def new_cmd(
        topic: str = typer.Argument(...),
        description: str | None = typer.Option(None, "--description"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_new(root, topic, description)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"created chunk topic: {result['path']}")

    @chunks_app.command("add")
    def add_cmd(
        topic: str = typer.Argument(...),
        files: list[Path] = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_add(root, topic, files)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"added to {result['id']}: {', '.join(result['added'])}")

    @chunks_app.command("list")
    def list_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        items = _do_list(root)
        if json_out:
            typer.echo(json.dumps({"ok": True, "items": items}, ensure_ascii=False))
        else:
            for it in items:
                typer.echo(f"{it['topic']}  [{it['status']}/{it['lang']}]")

    @chunks_app.command("show")
    def show_cmd(
        topic: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_show(root, topic)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"--- {result['topic']} ---")
            for k, v in result["frontmatter"].items():
                typer.echo(f"{k}: {v}")
            typer.echo("\nfiles:")
            for f in result["files"]:
                typer.echo(f"  {f}")
            typer.echo("")
            typer.echo(result["body"])

    @chunks_app.command("set-status")
    def set_status_cmd(
        topic: str = typer.Argument(...),
        status: str = typer.Argument(..., help="collecting | curating | ready"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_set_status(root, topic, status)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"{result['id']}: status → {status}")

    @chunks_app.command("rm")
    def rm_cmd(
        topic: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_rm(root, topic)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"removed {result['id']}")
```

- [ ] **Step 7.4: Modify `pkm/cli.py`** — add chunks registration in `_register_all()`:

```python
from pkm.commands import chunks as chunks_cmd
chunks_cmd.register(app)
```

- [ ] **Step 7.5: Run tests — must pass (~11 chunks tests)**

- [ ] **Step 7.6: Commit**

```bash
git add pkm/commands/chunks.py pkm/cli.py tests/test_chunks.py
git commit -m "M2.7: pkm chunks new/add/list/show/set-status/rm"
```

---

### Task 8: `pkm log` and `pkm index` CLI commands (TDD)

**Files:**
- Create: `pkm/commands/log.py`
- Create: `pkm/commands/index.py`
- Test: `tests/test_log_command.py`
- Test: `tests/test_index_command.py`
- Modify: `pkm/cli.py`

These commands wrap the primitives from Tasks 2 & 3.

`pkm log append <message> [--type TYPE] [--ref REF]` — append a manual event (rare, mostly for AI workflows that want to log non-CLI events).
`pkm log show [--since DATE] [--type TYPE] [--json]` — read+filter events.
`pkm index rebuild` — force a TOC regen (no-op if filesystem unchanged; fast).

#### Steps

- [ ] **Step 8.1: Write failing tests**

`tests/test_log_command.py`:
```python
"""Tests for pkm.commands.log."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def _init(tmp):
    runner.invoke(app, ["init", "--root", str(tmp)])


def test_log_append_basic(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(app, ["log", "append", "hello world",
                              "--type", "manual", "--ref", "n/a",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "manual" in log
    assert "hello world" in log


def test_log_show_json(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["log", "append", "m1", "--type", "t", "--ref", "r",
                        "--root", str(tmp_path)])
    res = runner.invoke(app, ["log", "show", "--json", "--root", str(tmp_path)])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert any(e["message"] == "m1" for e in payload["events"])


def test_log_show_filter_type(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["log", "append", "a", "--type", "x", "--ref", "1",
                        "--root", str(tmp_path)])
    runner.invoke(app, ["log", "append", "b", "--type", "y", "--ref", "2",
                        "--root", str(tmp_path)])
    res = runner.invoke(app, ["log", "show", "--type", "x", "--json",
                              "--root", str(tmp_path)])
    payload = json.loads(res.output)
    assert all(e["type"] == "x" for e in payload["events"])
```

`tests/test_index_command.py`:
```python
"""Tests for pkm.commands.index."""
from __future__ import annotations
from pathlib import Path

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def _init(tmp):
    runner.invoke(app, ["init", "--root", str(tmp)])


def test_index_rebuild_idempotent(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["index", "rebuild", "--root", str(tmp_path)])
    first = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    runner.invoke(app, ["index", "rebuild", "--root", str(tmp_path)])
    second = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert first == second
    assert "## Captures" in first
```

- [ ] **Step 8.2: Run tests — must fail**

- [ ] **Step 8.3: Write `pkm/commands/log.py`**

```python
"""`pkm log {append,show}` — manual access to data/log.md."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.store.log import LogEvent, append_event, read_events


def register(app: typer.Typer) -> None:
    log_app = typer.Typer(name="log", help="Inspect or extend data/log.md.", no_args_is_help=True)
    app.add_typer(log_app, name="log")

    @log_app.command("append")
    def append_cmd(
        message: str = typer.Argument(...),
        type_: str = typer.Option("manual", "--type", help="Event type."),
        ref: str = typer.Option("", "--ref", help="Reference id/slug."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        append_event(root, LogEvent(type=type_, ref=ref, message=message))
        if json_out:
            typer.echo(json.dumps({"ok": True, "stats": {"appended": 1}}, ensure_ascii=False))
        else:
            typer.echo(f"appended {type_} {ref}")

    @log_app.command("show")
    def show_cmd(
        type_filter: str | None = typer.Option(None, "--type"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        events = read_events(root, type_filter=type_filter)
        if json_out:
            typer.echo(json.dumps(
                {"ok": True, "events": [
                    {"timestamp": e.timestamp, "type": e.type, "ref": e.ref, "message": e.message}
                    for e in events
                ]},
                ensure_ascii=False,
            ))
        else:
            for e in events:
                typer.echo(f"{e.timestamp}  {e.type:<24}  {e.ref:<32}  {e.message}")
```

- [ ] **Step 8.4: Write `pkm/commands/index.py`**

```python
"""`pkm index rebuild` — regenerate data/index.md."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.store.toc import rebuild_index


def register(app: typer.Typer) -> None:
    idx_app = typer.Typer(name="index", help="Maintain data/index.md.", no_args_is_help=True)
    app.add_typer(idx_app, name="index")

    @idx_app.command("rebuild")
    def rebuild_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        rebuild_index(root)
        if json_out:
            typer.echo(json.dumps({"ok": True, "stats": {"path": "data/index.md"}}, ensure_ascii=False))
        else:
            typer.echo("rebuilt data/index.md")
```

- [ ] **Step 8.5: Modify `pkm/cli.py`** — register both:

```python
from pkm.commands import log as log_cmd
from pkm.commands import index as index_cmd
log_cmd.register(app)
index_cmd.register(app)
```

- [ ] **Step 8.6: Run tests — must pass**

- [ ] **Step 8.7: Commit**

```bash
git add pkm/commands/log.py pkm/commands/index.py pkm/cli.py tests/test_log_command.py tests/test_index_command.py
git commit -m "M2.8: pkm log {append,show} + pkm index rebuild"
```

---

### Task 9: Slash command templates + `pkm init` extension

**Files:**
- Create: `pkm/templates/.claude/commands/collect.md`
- Create: `pkm/templates/.claude/commands/research.md`
- Create: `pkm/templates/.claude/commands/review-captures.md`
- Modify: `pkm/commands/init.py` (extend `_FILES_FROM_TEMPLATES`)
- Modify: `pkm/templates/SCHEMA.md.template` (fill §3 frontmatter and §4 capture/chunks workflows)
- Modify: `tests/test_init.py` (assert the slash command files land)

#### Steps

- [ ] **Step 9.1: Write the three slash command templates**

These are the exact files to drop under `pkm/templates/.claude/commands/`. They are short by design (5–10 lines + SCHEMA reference per spec §4.2).

`pkm/templates/.claude/commands/collect.md`:
```markdown
# /collect <url|text>

Collect a single source into `data/raw/captures/`.

1. If input is a URL: WebFetch it; otherwise treat input as raw text.
2. Summarize in 1–3 sentences and infer 1–4 tags.
3. Run: `pkm capture create --slug <kebab-title> --title "<title>" --url <url-if-any> --status draft --json` (pipe the body through stdin).
4. Echo the returned `path`.

Workflow detail: SCHEMA.md § Workflows → "Collect".
```

`pkm/templates/.claude/commands/research.md`:
```markdown
# /research <topic>

Multi-source research. Parallel WebSearch + WebFetch + N captures.

1. Run a few WebSearch queries to fan out on the topic.
2. WebFetch the most relevant 3–6 URLs.
3. For each: `pkm capture create --slug <kebab> --title "<title>" --url <url> --status draft --json`.
4. Optionally bundle related sources into a chunk: `pkm chunks new <topic>` and `pkm chunks add <topic> <files>`.

Workflow detail: SCHEMA.md § Workflows → "Research".
```

`pkm/templates/.claude/commands/review-captures.md`:
```markdown
# /review-captures

Sweep all draft captures and either move them to `reviewed` or recommend deletion.

1. `pkm capture list --status draft --json` → iterate.
2. `pkm capture show <slug>` → inspect each.
3. For each capture, decide:
   - keep & promote later → `pkm capture set-status <slug> reviewed`
   - drop                 → `pkm capture rm <slug>`

Workflow detail: SCHEMA.md § Workflows → "Review Captures".
```

- [ ] **Step 9.2: Update `pkm/templates/SCHEMA.md.template`**

Replace the M1 placeholder sections §3 and §4 with the M2 fills below. (Keep §1, §2, §5, §6, §7 unchanged from M1.)

```markdown
## 3. Frontmatter

Two schemas land in M2. Wiki and writing schemas land in M4–M5.

### Capture (`data/raw/captures/*.md`)
- Required: `title`, `slug`, `created_at`, `status` (`draft|reviewed|archived`), `source_type` (`url|text|research`), `lang` (`ko|en|mixed`).
- Optional: `source_url`, `fetched_at`, `tags`, `summary`.

### Chunk README (`data/raw/chunks/<topic>/README.md`)
- Required: `topic`, `created_at`, `status` (`collecting|curating|ready`), `lang`, `sources` (list).
- Optional: `description`, `tags`.

## 4. Workflows

### Collect
- Input: a URL or pasted text.
- `pkm capture create --slug <s> --title "<t>" --url <u?> --status draft` (stdin = body).
- Result: a draft capture in `data/raw/captures/`.

### Research
- Input: a topic.
- Multiple WebSearch+WebFetch → `pkm capture create` per source. Bundle into `pkm chunks new <topic>` + `pkm chunks add` if it's a multi-source dive.

### Review captures
- `pkm capture list --status draft --json` → for each, `set-status reviewed` or `rm`.

### Chunk curation
- `pkm chunks new <topic>` → `pkm chunks add <topic> <file>...` → `pkm chunks set-status <topic> ready` once you've finished gathering.
```

(Sections 5 — CLI Reference, 6 — Invariants, 7 — Anti-patterns — remain as in M1.)

- [ ] **Step 9.3: Modify `pkm/commands/init.py`** — extend the templates list.

After the existing `_FILES_FROM_TEMPLATES` list, add the slash command templates. Path-relative entries (the template path key in `importlib.resources` uses `/` separators):

```python
_FILES_FROM_TEMPLATES: list[tuple[str, str]] = [
    ("SCHEMA.md", "SCHEMA.md.template"),
    (".pkm/config.toml", "config.toml.template"),
    (".claude/settings.json", "settings.json.template"),
    (".gitignore", "gitignore.template"),
    (".claude/commands/collect.md", ".claude/commands/collect.md"),
    (".claude/commands/research.md", ".claude/commands/research.md"),
    (".claude/commands/review-captures.md", ".claude/commands/review-captures.md"),
]
```

`_load_template` already uses `resources.files("pkm.templates").joinpath(name)` — `joinpath` accepts slash-separated paths, so this works without further changes.

- [ ] **Step 9.4: Update `tests/test_init.py`** — extend `_expected_paths` to include the three new files.

Insert into the returned list (before `root / ".gitignore"`):
```python
        root / ".claude" / "commands" / "collect.md",
        root / ".claude" / "commands" / "research.md",
        root / ".claude" / "commands" / "review-captures.md",
```

- [ ] **Step 9.5: Run full suite — all tests pass**

```bash
.venv/bin/pytest -v
```

- [ ] **Step 9.6: Commit**

```bash
git add pkm/templates/.claude/ pkm/templates/SCHEMA.md.template pkm/commands/init.py tests/test_init.py
git commit -m "M2.9: slash command templates + SCHEMA fill + pkm init wiring"
```

---

### Task 10: M2 verification & milestone tag

#### Steps

- [ ] **Step 10.1: Lint + type + tests**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/pyright
.venv/bin/pytest -v
```
Expected: ruff clean, pyright 0 errors, all tests pass. Total tests after M2 ≈ 37 (M1) + ~50 (M2) = ~87.

- [ ] **Step 10.2: End-to-end smoke**

```bash
mkdir -p /tmp/pkm-m2-final && cd /tmp/pkm-m2-final
PKM=/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm

$PKM init
echo "본문 내용입니다" | $PKM capture create --slug oauth --title "OAuth 토큰 저장" --status draft --json
$PKM capture list --json | python -m json.tool
$PKM capture set-status oauth reviewed
$PKM capture show oauth | head -10

$PKM chunks new oauth-deep-dive --description "OAuth 토큰 보안 자료"
echo "ref-source" > /tmp/refsrc.md
$PKM chunks add oauth-deep-dive /tmp/refsrc.md
$PKM chunks list --json | python -m json.tool

$PKM log show | head -10
$PKM index rebuild
cat data/index.md | head -30

$PKM doctor --strict
echo "EXIT_DOCTOR=$?"

cd - && rm -rf /tmp/pkm-m2-final /tmp/refsrc.md
```
Expected: all commands exit 0; log.md and index.md grow with each mutation; doctor --strict exits 0.

- [ ] **Step 10.3: Tag milestone**

```bash
cd /Users/ad03159868/Downloads/Claude_lab/hwi_PKM
git tag -a m2-capture-chunks -m "M2: Capture/Chunks complete — pkm capture *, pkm chunks *, log/index auto-update, slash command templates"
```

- [ ] **Step 10.4: Update `README.md`** — mark M2 done.

Change `- [ ] M2 — Capture & Chunks` to `- [x] M2 — Capture & Chunks`. Commit:
```bash
git add README.md
git commit -m "M2.10: mark M2 complete in README"
```

---

## Acceptance criteria for M2

- [ ] `pkm capture create --slug X --title T` writes a date-prefixed capture file with valid frontmatter (capture schema).
- [ ] `pkm capture create --json` returns `{"ok":true,"id":...,"path":...}`.
- [ ] Body source: stdin by default; `--from-file PATH` overrides.
- [ ] `--url` toggles `source_type: url` and adds `source_url`/`fetched_at`.
- [ ] Refuses to overwrite an existing capture (no `--force` in M2).
- [ ] `pkm capture list [--status][--lang]` works with and without `--json`.
- [ ] `pkm capture show <id-or-slug>` resolves exact and substring matches; ambiguous matches fail with `VALIDATION_ERROR`.
- [ ] `pkm capture set-status` rejects values outside the enum.
- [ ] `pkm capture rm` deletes the file and logs `capture.rm`.
- [ ] `pkm chunks new <topic>` creates `data/raw/chunks/<topic>/README.md` with chunk frontmatter (status `collecting`).
- [ ] `pkm chunks add <topic> <file>...` copies files into the topic dir and appends to `sources:`.
- [ ] `pkm chunks {list,show,set-status,rm}` mirror the capture analogues.
- [ ] Every mutation appends a single row to `data/log.md` (column-aligned table) and triggers `data/index.md` regeneration.
- [ ] `pkm log {append,show}` and `pkm index rebuild` are wired and `--json` produces the expected shape.
- [ ] `pkm init` now seeds `.claude/commands/{collect,research,review-captures}.md`.
- [ ] `pkm doctor --strict` on a freshly initialized + populated repo exits 0.
- [ ] Tests: ~87 passing (M1 37 + M2 ~50). Ruff clean, pyright clean.
- [ ] Tag `m2-capture-chunks` annotated.
- [ ] 10 numbered commits with `M2.<N>:` prefix.

---

## Definition of Done

A user (or AI agent) can sit in a Claude Code session and produce a populated PKM:
1. `pkm init`
2. `/collect https://...` (or manually `pkm capture create ...`)
3. `pkm capture list` → review → `pkm capture set-status <slug> reviewed`
4. (optional) `pkm chunks new <topic>` + `pkm chunks add <topic> <files>` to bundle reference materials
5. `data/log.md` and `data/index.md` are kept current automatically

M3 (Indexing & Search) can begin from this state without revisiting M2 infrastructure.

---

## Notes for the executor

- **Skill priorities**:
  - `superpowers:test-driven-development` — Tasks 1–8 are TDD. Red → green → refactor → commit.
  - `superpowers:verification-before-completion` — run the exact verification commands shown.
- **DRY**: `_emit_or_raise` (chunks.py) and the inline error-handling in `capture.py` do similar work. If you find yourself writing a third copy in `log.py` or elsewhere, extract a `pkm.commands._common.emit_error_or_exit(json_out, exc)` helper. M2 keeps both inline because the surface is small enough.
- **YAGNI**: do not add `pkm extract`, `pkm capture create --force`, status-transition validation (e.g., disallow `archived → draft`), or git auto-commit. Those land in later milestones.
- **Commit frequency**: after every task, never larger. The 10-commit shape lets the reviewer step through them in order.
- **Stdin handling under CliRunner**: `runner.invoke(app, [...], input="body")` feeds `sys.stdin`. The capture create test relies on this; if a future test fails because stdin is empty, check that `input=` is set and the implementation reads from `sys.stdin.read()` rather than blocking on `input()`.
- **For M3 planner (note)**: this milestone introduces the auto-update chokepoint at `pkm/_mutations.py:post_mutation`. M3 should extend it — not bypass it — when adding git auto-commit and reindex hooks. Keep the surface single-function so the four side-effects (log, index, git, reindex) chain in known order: `log → index → git → reindex`.
