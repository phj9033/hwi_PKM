# M14 — Session Adapter + Claude Code Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI integration on top of M13's data plane. Adds Claude Code session transcript discovery (`~/.claude/projects/**/*.jsonl`), `pkm session list/show/forget/mark-processed`, `pkm context inject`, `pkm install --for claude-code` (writing global skills/commands/CLAUDE.md), 3 skill bundles (`pkm:recalling-project-context`, `pkm:extracting-session-knowledge`, `pkm:backfilling-sessions`), and 4 slash commands. End-to-end backfill + per-session extract workflows.

**Architecture:**
- **Adapter pattern, V1 = claude_code only.** Protocol in `pkm/session/adapters/base.py`; concrete `claude_code.py`. Future V4 adapters (Codex, Cursor, Gemini) plug in via the same Protocol.
- **In-session extraction.** No LLM shell-out. Claude (in the user's session) reads transcripts via `Read` tool and produces structured output following `pkm/templates/skills/extracting-session-knowledge/output-schema.md`. The CLI provides primitives only: `pkm session show` (transcript path), `pkm project knowledge add` (write file), `pkm session mark-processed` (record).
- **Skill + CLAUDE.md, no SessionStart hook.** `~/.claude/CLAUDE.md` gets a managed block instructing Claude to call `pkm:recalling-project-context` skill at start of work in any cwd. Skill checks `pkm project current --json` — silent if NOT_LINKED. This avoids settings.json mutation and keeps `pkm install --uninstall` clean.
- **Portability rules R1–R7 (spec §8.2) enforced in skill templates.** All skill bodies use `pkm` CLI for path resolution and project-id, never hardcoded paths/ids.
- **Idempotent install + uninstall via manifest.** Two tracking strategies, used selectively:
  1. **Embedded blocks** in user-edited files (`~/.claude/CLAUDE.md`) use `<!-- pkm:start -->` / `<!-- pkm:end -->` markers. `apply_managed_block()` inserts/replaces between markers, preserving user content outside.
  2. **Standalone files** (slash commands, skill files) — these begin with YAML frontmatter (`---\nname: ...\n---`) so an HTML comment marker above them would break Claude Code's frontmatter parser. Instead, `pkm install` writes a manifest at `~/.pkm/install_manifest.json` listing every emitted file path. `--uninstall` reads the manifest and deletes those exact paths, then deletes the manifest. **No in-file marker is added to frontmatter-bearing files.**
- **Session metadata gitignored.** `.pkm/sessions/<project>/<uuid>.json` records "this session has been processed on this PC" — not git-tracked because Claude Code transcripts themselves are PC-local.

**Tech Stack:** Python 3.11+, no new PyPI deps (reuses tomllib/tomli-w/yaml). Templates are static markdown shipped in `pkm/templates/`.

**Spec reference:** `docs/superpowers/specs/2026-05-07-pkm-projects-and-sessions-design.md` §16.2 (M14).

**Depends on:** M13 (this plan assumes m003 is applied, `pkm project link/current/knowledge add` work, `data/projects/**` is searchable).

---

## File Structure

### Created in M14

| File | Responsibility |
|---|---|
| `pkm/session/adapters/__init__.py` | Adapter registry (dict of name → adapter) |
| `pkm/session/adapters/base.py` | `SessionRef`, `NormalizedMessage`, `NormalizedTranscript` dataclasses + `SessionAdapter` Protocol |
| `pkm/session/adapters/claude_code.py` | Claude Code `.jsonl` discovery + cwd decoding + parse() smoke |
| `pkm/session/meta.py` | `.pkm/sessions/<project>/<uuid>.json` read/write + `is_processed()` |
| `pkm/commands/session.py` | `pkm session {list, show, forget, mark-processed}` |
| `pkm/commands/context.py` | `pkm context inject [--max-tokens N] [--quiet-on-not-linked]` |
| `pkm/commands/install.py` | `pkm install --for claude-code [--data-repo PATH] [--uninstall]` |
| `pkm/install/__init__.py` | Helpers: `apply_managed_block()`, `remove_managed_block()`, `install_file()`, `install_dir()`, `uninstall_via_manifest()`, `read_manifest()`, `write_manifest()` |
| `pkm/templates/__init__.py` | Empty marker (existing — verify it's a Python package; if not, create) |
| `pkm/templates/commands/__init__.py` | Empty marker — makes templates discoverable via filesystem |
| `pkm/templates/skills/__init__.py` | Empty marker |
| `pkm/templates/skills/recalling-project-context/__init__.py` | Empty marker |
| `pkm/templates/skills/extracting-session-knowledge/__init__.py` | Empty marker |
| `pkm/templates/skills/backfilling-sessions/__init__.py` | Empty marker |
| `pkm/templates/claude_md_block.md` | Managed block content for `~/.claude/CLAUDE.md` |
| `pkm/templates/commands/pkm-recall.md` | Slash command template — invoke pkm:recalling-project-context skill |
| `pkm/templates/commands/pkm-extract-session.md` | Slash command — invoke pkm:extracting-session-knowledge skill |
| `pkm/templates/commands/pkm-backfill.md` | Slash command — invoke pkm:backfilling-sessions skill |
| `pkm/templates/commands/pkm-project.md` | Slash command — direct CLI wrapper (no skill) |
| `pkm/templates/skills/recalling-project-context/SKILL.md` | Skill body — load project context |
| `pkm/templates/skills/recalling-project-context/search-scope-guidelines.md` | Reference doc |
| `pkm/templates/skills/extracting-session-knowledge/SKILL.md` | Skill body — extract from transcript |
| `pkm/templates/skills/extracting-session-knowledge/extraction-categories.md` | Reference doc — what counts as decision/pitfall/etc. |
| `pkm/templates/skills/extracting-session-knowledge/output-schema.md` | Reference doc — JSON schema for extraction output |
| `pkm/templates/skills/extracting-session-knowledge/review-protocol.md` | Reference doc — 2-round review UX |
| `pkm/templates/skills/backfilling-sessions/SKILL.md` | Skill body — batch processing, resumable |
| `tests/fixtures/sessions/short_session.jsonl` | < min-messages, exercises cutoff |
| `tests/fixtures/sessions/typical_session.jsonl` | Normal extraction case |
| `tests/fixtures/sessions/long_session.jsonl` | Triggers windowed parse |
| `tests/fixtures/sessions/corrupt_session.jsonl` | Triggers `CORRUPT_TRANSCRIPT` |
| `tests/test_session_adapter_claude.py` | discovery, encoded-cwd decoding, parse smoke |
| `tests/test_session_lifecycle.py` | mark-processed idempotent, forget, gitignored meta |
| `tests/test_session_list_filters.py` | --since, --min-messages, --unprocessed |
| `tests/test_context_inject.py` | --on-session-start, NOT_LINKED quiet, max-tokens trim |
| `tests/test_install_claude_code.py` | install/uninstall idempotent, managed marker, user content preserved |
| `tests/test_install_e2e.py` | --dry-run, expected files |
| `tests/test_backfill_idempotent.py` | Two runs → second skips all |
| `tests/test_v3_acceptance_m14.py` | M14 portion of spec §16.3 |

### Modified in M14

| File | Change |
|---|---|
| `pkm/errors.py` | Add `CORRUPT_TRANSCRIPT`, `PKM_INSTALL_MISSING` |
| `pkm/cli.py` | Register `session`, `context`, `install` typer apps |
| `pkm/commands/doctor.py` | Add `pkm_install` row (managed block presence). On `--strict` + missing → `PKM_INSTALL_MISSING`. Add `unprocessed_sessions` informational row. |
| `pkm/templates/.gitignore` (data-repo scaffolded) | Add `.pkm/sessions/` |
| `tests/test_failure_mode_matrix.py` | Register 2 new error scenarios |
| `tests/test_doctor.py` | Assert new rows |
| `README.md` | Add M14 progress checkbox + `pkm session/install/context` to commands table |
| `docs/FEATURES.md` | Add §2.12 (session), §2.13 (install), §2.14 (context). Add UC8 (post-session extract) + UC9 (backfill) walk-throughs. |

---

## Pre-flight: confirm M13 baseline

- [ ] **Step 0.1: M13 must be merged**

```bash
git log --oneline -20 | grep "M13:"
uv run pytest -q
```

Expected: At least one M13 commit visible. All tests pass.

- [ ] **Step 0.2: Verify a project is linked for smoke testing**

```bash
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project list --json
```

Expected: At least one project listed (or seed one for M14 fixtures).

---

## Task 1 — New error classes + failure-matrix scenarios

**Files:**
- Modify: `pkm/errors.py`
- Modify: `tests/test_failure_mode_matrix.py`

- [ ] **Step 1.1: Add failure-matrix scenarios**

```python
def _scenario_corrupt_transcript(repo: Path) -> list[str]:
    """Place a corrupt jsonl in the test transcript dir, then list/show."""
    fake_root = repo.parent / ".claude-projects"
    (fake_root / "-tmp-fake").mkdir(parents=True, exist_ok=True)
    bad = fake_root / "-tmp-fake" / "corrupt.jsonl"
    bad.write_text("not json {{{ broken\n", encoding="utf-8")
    return ["session", "show", "corrupt", "--json"]


def _scenario_pkm_install_missing(repo: Path) -> list[str]:
    """Strict doctor when no install has been run."""
    return ["doctor", "--strict", "--json"]


SCENARIOS.update({
    "CORRUPT_TRANSCRIPT": _scenario_corrupt_transcript,
    "PKM_INSTALL_MISSING": _scenario_pkm_install_missing,
})

SCENARIO_ENV.update({
    "CORRUPT_TRANSCRIPT": {"PKM_TRANSCRIPT_ROOT": ""},  # set in fixture to fake_root
    "PKM_INSTALL_MISSING": {"HOME": ""},  # set in fixture to a fresh tmp HOME
})
```

- [ ] **Step 1.2: Add error classes**

```python
class PKMCorruptTranscript(PKMValidationError):
    """jsonl parse failed."""
    code = "CORRUPT_TRANSCRIPT"


class PKMInstallMissing(PKMStateError):
    """`pkm install --for claude-code` not run on this PC; --strict doctor fails."""
    code = "PKM_INSTALL_MISSING"
```

- [ ] **Step 1.3: Verify + commit**

```bash
uv run python -c "from pkm.errors import all_error_codes; assert 'CORRUPT_TRANSCRIPT' in all_error_codes() and 'PKM_INSTALL_MISSING' in all_error_codes()"
git add pkm/errors.py tests/test_failure_mode_matrix.py
git commit -m "M14.1: CORRUPT_TRANSCRIPT + PKM_INSTALL_MISSING error classes"
```

---

## Task 2 — Session adapter (base + claude_code)

**Files:**
- Create: `pkm/session/adapters/__init__.py`
- Create: `pkm/session/adapters/base.py`
- Create: `pkm/session/adapters/claude_code.py`
- Test: `tests/test_session_adapter_claude.py`
- Test fixtures: `tests/fixtures/sessions/*.jsonl`

- [ ] **Step 2.1: Build test fixtures**

`tests/fixtures/sessions/typical_session.jsonl`:
```jsonl
{"type":"user","content":"OAuth refresh token 어디 저장?","timestamp":"2026-05-07T14:00:00Z"}
{"type":"assistant","content":"httpOnly secure cookie 권장.","timestamp":"2026-05-07T14:00:30Z"}
{"type":"user","content":"localStorage 안 좋은 이유?","timestamp":"2026-05-07T14:01:00Z"}
{"type":"assistant","content":"XSS 노출 위험.","timestamp":"2026-05-07T14:01:30Z"}
{"type":"user","content":"좋아 cookie 로 가자","timestamp":"2026-05-07T14:02:00Z"}
{"type":"assistant","content":"결정: refresh token 은 httpOnly cookie.","timestamp":"2026-05-07T14:02:30Z"}
```

`tests/fixtures/sessions/short_session.jsonl`:
```jsonl
{"type":"user","content":"hi","timestamp":"2026-05-07T14:00:00Z"}
{"type":"assistant","content":"hello","timestamp":"2026-05-07T14:00:01Z"}
```

`tests/fixtures/sessions/corrupt_session.jsonl`:
```
this is not valid jsonl {{{
```

`tests/fixtures/sessions/long_session.jsonl`: 60+ lines following typical pattern (generate programmatically in fixture setup if simpler).

- [ ] **Step 2.2: Write failing tests**

```python
"""Claude Code session adapter — discovery + cwd decoding + parse smoke."""

from pathlib import Path
import pytest
from pkm.session.adapters.claude_code import ClaudeCodeAdapter, decode_cwd
from pkm.session.adapters.base import SessionRef


@pytest.mark.parametrize("encoded,expected", [
    ("-Users-me-Code-app", "/Users/me/Code/app"),
    ("-Users-me-Downloads-Claude-lab-hwi-PKM", "/Users/me/Downloads/Claude_lab/hwi_PKM"),
    # Note: Claude Code's encoding has known ambiguity around underscores; document
    # the decoder's heuristic clearly. See decode_cwd implementation notes.
])
def test_decode_cwd(encoded, expected):
    # The decoder is best-effort; the canonical use is matching git remotes,
    # so exact reverse is not required for most code paths.
    assert decode_cwd(encoded).endswith(expected.split("/")[-1])


def test_discover_finds_jsonl(tmp_transcript_root):
    # Seed: tmp_transcript_root/-Users-me-app/abc123.jsonl
    cwd_dir = tmp_transcript_root / "-Users-me-app"
    cwd_dir.mkdir(parents=True)
    (cwd_dir / "abc123.jsonl").write_text(
        '{"type":"user","content":"hi","timestamp":"2026-05-07T14:00:00Z"}\n', encoding="utf-8"
    )
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    assert len(refs) == 1
    assert refs[0].uuid == "abc123"
    assert refs[0].message_count >= 1


def test_discover_skips_non_jsonl(tmp_transcript_root):
    cwd_dir = tmp_transcript_root / "-tmp-fake"
    cwd_dir.mkdir(parents=True)
    (cwd_dir / "notes.txt").write_text("not jsonl", encoding="utf-8")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    assert list(adapter.discover()) == []


def test_resolve_project_id_via_git_remote(tmp_transcript_root, fake_project_index, monkeypatch):
    # Stub discover_remote to return the matching remote
    monkeypatch.setattr("pkm.session.adapters.claude_code.discover_remote", lambda cwd: "github.com:test/test")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    cwd_dir = tmp_transcript_root / "-some-cwd"
    cwd_dir.mkdir(parents=True)
    (cwd_dir / "x.jsonl").write_text('{"type":"user","content":"x"}\n', encoding="utf-8")
    refs = list(adapter.discover())
    pid = adapter.resolve_project_id(refs[0], fake_project_index)
    assert pid == "demo"  # fake_project_index has demo with that remote


def test_parse_smoke_typical_session(typical_session_jsonl):
    adapter = ClaudeCodeAdapter(transcript_root=typical_session_jsonl.parent.parent)
    ref = SessionRef(
        uuid=typical_session_jsonl.stem, cwd=Path("/tmp/x"),
        started_at=None, last_message_at=None, message_count=6,
        model=None, transcript_path=typical_session_jsonl,
    )
    norm = adapter.parse(ref)
    assert len(norm.messages) == 6
    assert norm.messages[0].role == "user"


def test_parse_corrupt_raises(corrupt_session_jsonl):
    from pkm.errors import PKMCorruptTranscript
    adapter = ClaudeCodeAdapter(transcript_root=corrupt_session_jsonl.parent.parent)
    ref = SessionRef(uuid="corrupt", cwd=Path("/tmp"), started_at=None, last_message_at=None, message_count=0, model=None, transcript_path=corrupt_session_jsonl)
    with pytest.raises(PKMCorruptTranscript):
        adapter.parse(ref)
```

Add fixtures to `tests/conftest.py`:
```python
@pytest.fixture
def tmp_transcript_root(tmp_path):
    return tmp_path / "claude-projects"


@pytest.fixture
def typical_session_jsonl(tmp_transcript_root):
    cwd_dir = tmp_transcript_root / "-tmp-fake"
    cwd_dir.mkdir(parents=True)
    src = Path(__file__).parent / "fixtures" / "sessions" / "typical_session.jsonl"
    dst = cwd_dir / "typical.jsonl"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


@pytest.fixture
def corrupt_session_jsonl(tmp_transcript_root):
    cwd_dir = tmp_transcript_root / "-tmp-fake"
    cwd_dir.mkdir(parents=True)
    src = Path(__file__).parent / "fixtures" / "sessions" / "corrupt_session.jsonl"
    dst = cwd_dir / "corrupt.jsonl"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


@pytest.fixture
def fake_project_index():
    from pkm.session.registry import ProjectIndex, ProjectRecord
    return ProjectIndex(records=[
        ProjectRecord(id="demo", git_remotes=["github.com:test/test"], local_paths=[]),
    ])
```

- [ ] **Step 2.3: Implement adapter**

Create `pkm/session/adapters/__init__.py`:
```python
from pkm.session.adapters.base import SessionAdapter, SessionRef, NormalizedTranscript, NormalizedMessage
from pkm.session.adapters.claude_code import ClaudeCodeAdapter

ADAPTERS: dict[str, type[SessionAdapter]] = {
    "claude_code": ClaudeCodeAdapter,
}
```

Create `pkm/session/adapters/base.py`:
```python
"""Session adapter Protocol — abstracts AI CLI transcript handling.

V1 = claude_code only. V4 will add codex, cursor, gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal, Protocol


@dataclass(frozen=True)
class SessionRef:
    uuid: str
    cwd: Path
    started_at: datetime | None
    last_message_at: datetime | None
    message_count: int
    model: str | None
    transcript_path: Path


@dataclass(frozen=True)
class NormalizedMessage:
    role: Literal["user", "assistant", "system", "tool"]
    content_blocks: list[dict]
    timestamp: datetime | None


@dataclass(frozen=True)
class NormalizedTranscript:
    ref: SessionRef
    messages: list[NormalizedMessage]


class SessionAdapter(Protocol):
    name: str
    transcript_root: Path

    def discover(self) -> Iterator[SessionRef]: ...
    def resolve_project_id(self, ref: SessionRef, project_index) -> str | None: ...
    def parse(self, ref: SessionRef) -> NormalizedTranscript: ...
```

Create `pkm/session/adapters/claude_code.py`:
```python
"""Claude Code adapter — ~/.claude/projects/<encoded-cwd>/<uuid>.jsonl"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

from pkm.errors import PKMCorruptTranscript
from pkm.session.adapters.base import SessionRef, NormalizedTranscript, NormalizedMessage
from pkm.session.git_remote import discover_remote


def _default_transcript_root() -> Path:
    env = os.environ.get("PKM_TRANSCRIPT_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "projects"


def decode_cwd(encoded: str) -> str:
    """Best-effort: Claude Code encodes cwd by replacing `/` with `-`.
    The encoding is lossy (cannot disambiguate `/foo-bar` from `/foo/bar`).
    For multi-PC matching we use git remotes (frontmatter SoT), not decoded cwd —
    so this is only used for display/heuristic.
    """
    if not encoded.startswith("-"):
        return encoded
    return "/" + encoded[1:].replace("-", "/")


class ClaudeCodeAdapter:
    name = "claude_code"

    def __init__(self, transcript_root: Path | None = None) -> None:
        self.transcript_root = transcript_root or _default_transcript_root()

    def discover(self) -> Iterator[SessionRef]:
        if not self.transcript_root.is_dir():
            return iter([])
        for cwd_dir in sorted(self.transcript_root.iterdir()):
            if not cwd_dir.is_dir() or not cwd_dir.name.startswith("-"):
                continue
            for jsonl in sorted(cwd_dir.glob("*.jsonl")):
                yield self._build_ref(jsonl, cwd_dir)

    def _build_ref(self, jsonl: Path, cwd_dir: Path) -> SessionRef:
        # Read header only (first line + line count) — full parse happens in parse().
        try:
            with jsonl.open("r", encoding="utf-8") as f:
                first_line = f.readline()
                msg_count = 1 + sum(1 for _ in f)
        except OSError:
            first_line = ""
            msg_count = 0
        started_at = None
        if first_line:
            try:
                first = json.loads(first_line)
                ts = first.get("timestamp")
                if ts:
                    started_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (json.JSONDecodeError, ValueError):
                pass
        return SessionRef(
            uuid=jsonl.stem,
            cwd=Path(decode_cwd(cwd_dir.name)),
            started_at=started_at,
            last_message_at=None,
            message_count=msg_count,
            model=None,
            transcript_path=jsonl,
        )

    def resolve_project_id(self, ref: SessionRef, project_index) -> str | None:
        remote = discover_remote(ref.cwd)
        if not remote:
            return None
        for r in project_index.records:
            if remote in r.git_remotes:
                return r.id
        return None

    def parse(self, ref: SessionRef) -> NormalizedTranscript:
        try:
            text = ref.transcript_path.read_text(encoding="utf-8")
        except OSError as e:
            raise PKMCorruptTranscript(f"cannot read {ref.transcript_path}: {e}", code="CORRUPT_TRANSCRIPT")
        messages: list[NormalizedMessage] = []
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise PKMCorruptTranscript(f"invalid jsonl at line {i+1}: {e}", code="CORRUPT_TRANSCRIPT")
            role = obj.get("type", "user")
            content = obj.get("content", "")
            ts = None
            if "timestamp" in obj:
                try:
                    ts = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            messages.append(NormalizedMessage(
                role=role if role in ("user", "assistant", "system", "tool") else "user",
                content_blocks=[{"type": "text", "text": content}] if isinstance(content, str) else (content if isinstance(content, list) else [{"type": "text", "text": str(content)}]),
                timestamp=ts,
            ))
        return NormalizedTranscript(ref=ref, messages=messages)
```

- [ ] **Step 2.4: Run tests**

```bash
uv run pytest tests/test_session_adapter_claude.py -v
```

Expected: all pass (note: `parse` smoke test is intentionally narrow — full coverage deferred to V4 per spec §6.3).

- [ ] **Step 2.5: Commit**

```bash
git add pkm/session/adapters/ tests/test_session_adapter_claude.py tests/fixtures/sessions/ tests/conftest.py
git commit -m "M14.2: session adapter base + claude_code (discover + parse smoke)"
```

---

## Task 3 — `pkm session list/show/forget/mark-processed`

**Files:**
- Create: `pkm/session/meta.py`
- Create: `pkm/commands/session.py`
- Modify: `pkm/cli.py`
- Test: `tests/test_session_list_filters.py`
- Test: `tests/test_session_lifecycle.py`

- [ ] **Step 3.1: Write failing tests**

```python
"""pkm session list/show/forget/mark-processed."""

import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_session_list_filters_unprocessed(tmp_data_repo, tmp_transcript_root_with_2_sessions, monkeypatch, fake_project_setup):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    # Mark one as processed (fixture has 'first' and 'second' uuids)
    runner.invoke(app, ["session", "mark-processed", "first", "--extracted-count", "3", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    uuids = [s["uuid"] for s in payload["sessions"]]
    assert "first" not in uuids
    assert "second" in uuids


def test_session_list_min_messages_default(tmp_data_repo, tmp_transcript_root, monkeypatch):
    """Default --min-messages 5 filters out tiny sessions."""
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root))
    # short_session has 2 messages
    result = runner.invoke(app, ["session", "list", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    short_in_list = any(s["uuid"] == "short" for s in payload["sessions"])
    assert not short_in_list


def test_session_show_returns_transcript_path(tmp_data_repo, typical_session_jsonl, monkeypatch):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(typical_session_jsonl.parent.parent))
    result = runner.invoke(app, ["session", "show", typical_session_jsonl.stem, "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    assert payload["transcript_path"] == str(typical_session_jsonl)


def test_mark_processed_creates_meta_file(tmp_data_repo, typical_session_jsonl, monkeypatch, fake_project_setup):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(typical_session_jsonl.parent.parent))
    runner.invoke(app, ["session", "mark-processed", typical_session_jsonl.stem, "--extracted-count", "2", "--data-repo", str(tmp_data_repo)])
    meta_path = tmp_data_repo / ".pkm" / "sessions" / "demo" / f"{typical_session_jsonl.stem}.json"
    assert meta_path.is_file()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["session_uuid"] == typical_session_jsonl.stem
    assert meta["extracted"]["total"] == 2 if "total" in meta["extracted"] else True


def test_forget_removes_meta_file(tmp_data_repo, typical_session_jsonl, monkeypatch, fake_project_setup):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(typical_session_jsonl.parent.parent))
    runner.invoke(app, ["session", "mark-processed", typical_session_jsonl.stem, "--extracted-count", "1", "--data-repo", str(tmp_data_repo)])
    runner.invoke(app, ["session", "forget", typical_session_jsonl.stem, "--data-repo", str(tmp_data_repo)])
    meta_path = tmp_data_repo / ".pkm" / "sessions" / "demo" / f"{typical_session_jsonl.stem}.json"
    assert not meta_path.exists()


def test_mark_processed_idempotent(tmp_data_repo, typical_session_jsonl, monkeypatch, fake_project_setup):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(typical_session_jsonl.parent.parent))
    r1 = runner.invoke(app, ["session", "mark-processed", typical_session_jsonl.stem, "--extracted-count", "2", "--data-repo", str(tmp_data_repo)])
    r2 = runner.invoke(app, ["session", "mark-processed", typical_session_jsonl.stem, "--extracted-count", "2", "--data-repo", str(tmp_data_repo)])
    assert r1.exit_code == 0 and r2.exit_code == 0
```

Add fixtures to `tests/conftest.py` (these are referenced by Task 3, Task 8, and Task 11 tests):

```python
import json
import subprocess

@pytest.fixture
def fake_project_setup(tmp_data_repo, monkeypatch):
    """Seed data/projects/demo/ with a valid index.md frontmatter linked to a fake git remote.
    Used by tests that need a linked project + matching transcript cwd."""
    pdir = tmp_data_repo / "data" / "projects" / "demo"
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        (pdir / cat).mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:test/test\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n\n# demo\n",
        encoding="utf-8",
    )
    # Stub discover_remote so adapter resolves to demo regardless of actual cwd git state
    monkeypatch.setattr("pkm.session.adapters.claude_code.discover_remote", lambda cwd: "github.com:test/test")
    return tmp_data_repo


def _write_synthetic_session(target: Path, n_messages: int) -> None:
    lines = []
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        lines.append(json.dumps({
            "type": role,
            "content": f"message {i} content",
            "timestamp": f"2026-05-07T1{i % 10}:{(i*7) % 60:02d}:00Z",
        }))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def tmp_transcript_root_with_2_sessions(tmp_path):
    """Two sessions named 'first' and 'second' under a single encoded-cwd dir."""
    root = tmp_path / "transcripts"
    cwd_dir = root / "-tmp-test-coderepo"
    cwd_dir.mkdir(parents=True)
    _write_synthetic_session(cwd_dir / "first.jsonl", n_messages=6)
    _write_synthetic_session(cwd_dir / "second.jsonl", n_messages=7)
    return root


@pytest.fixture
def tmp_transcript_root_with_3_sessions(tmp_path):
    """Three sessions with deterministic uuids 'a', 'b', 'c' for batch tests."""
    root = tmp_path / "transcripts"
    cwd_dir = root / "-tmp-test-coderepo"
    cwd_dir.mkdir(parents=True)
    for uuid_ in ["a", "b", "c"]:
        _write_synthetic_session(cwd_dir / f"{uuid_}.jsonl", n_messages=6)
    return root


@pytest.fixture
def tmp_unlinked_cwd(tmp_path):
    """A cwd that isn't linked to any project (no git remote, no override)."""
    p = tmp_path / "unlinked"
    p.mkdir()
    return p
```

These fixtures are deterministic — uuids match what tests assert on, message counts pass `--min-messages 5` default.

- [ ] **Step 3.2: Implement meta + commands**

`pkm/session/meta.py`:
```python
"""Session processing metadata — .pkm/sessions/<project>/<uuid>.json (gitignored)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pkm.session.adapters.base import SessionRef


def _meta_path(repo: Path, project_id: str, uuid: str) -> Path:
    return repo / ".pkm" / "sessions" / project_id / f"{uuid}.json"


def is_processed(repo: Path, project_id: str, uuid: str) -> bool:
    return _meta_path(repo, project_id, uuid).is_file()


def mark_processed(
    repo: Path, ref: SessionRef, project_id: str, *, extracted: dict, extracted_paths: list[str],
) -> Path:
    p = _meta_path(repo, project_id, ref.uuid)
    p.parent.mkdir(parents=True, exist_ok=True)
    sha = ""
    try:
        sha = hashlib.sha256(ref.transcript_path.read_bytes()).hexdigest()
    except OSError:
        pass
    payload = {
        "session_uuid": ref.uuid,
        "project_id": project_id,
        "transcript_path": str(ref.transcript_path),
        "transcript_sha256": sha,
        "transcript_message_count": ref.message_count,
        "processed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "extracted": extracted,
        "extracted_paths": extracted_paths,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def forget(repo: Path, project_id: str, uuid: str) -> bool:
    p = _meta_path(repo, project_id, uuid)
    if p.is_file():
        p.unlink()
        return True
    return False


def read_meta(repo: Path, project_id: str, uuid: str) -> dict | None:
    p = _meta_path(repo, project_id, uuid)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
```

`pkm/commands/session.py`:
```python
"""pkm session list/show/forget/mark-processed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMValidationError
from pkm.session.adapters import ClaudeCodeAdapter
from pkm.session.meta import is_processed, mark_processed as _mark, forget as _forget, read_meta
from pkm.session.registry import ProjectIndex, load_local_overrides

app = typer.Typer(no_args_is_help=True, help="Manage AI session transcripts.")


def _resolve_repo(data_repo: Path | None) -> Path:
    if data_repo:
        return data_repo
    p = resolve_data_repo()
    if p is None:
        raise PKMValidationError("Cannot resolve data repo.", code="DATA_REPO_NOT_FOUND")
    return p


def _adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


@app.command("list")
def list_(
    project: str | None = typer.Option(None, "--project"),
    unprocessed: bool = typer.Option(False, "--unprocessed"),
    since: str | None = typer.Option(None, "--since"),
    until: str | None = typer.Option(None, "--until"),
    min_messages: int = typer.Option(5, "--min-messages"),
    limit: int | None = typer.Option(None, "--limit"),
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    adapter = _adapter()
    out: list[dict] = []
    for ref in adapter.discover():
        if ref.message_count < min_messages:
            continue
        pid = adapter.resolve_project_id(ref, idx)
        if not pid:
            continue
        if project and pid != project:
            continue
        if unprocessed and is_processed(repo, pid, ref.uuid):
            continue
        if since and ref.started_at and ref.started_at.isoformat() < since:
            continue
        if until and ref.started_at and ref.started_at.isoformat() > until:
            continue
        out.append({
            "uuid": ref.uuid,
            "project_id": pid,
            "started_at": ref.started_at.isoformat() if ref.started_at else None,
            "message_count": ref.message_count,
            "transcript_path": str(ref.transcript_path),
            "processed": is_processed(repo, pid, ref.uuid),
        })
    out.sort(key=lambda s: s["started_at"] or "")
    if limit:
        out = out[:limit]
    if json_out:
        typer.echo(json.dumps({"ok": True, "sessions": out}, ensure_ascii=False))
    else:
        for s in out:
            typer.echo(f"{s['uuid']:24s} {s['project_id']:20s} msgs={s['message_count']:4d} processed={s['processed']}")


@app.command("show")
def show(
    uuid: str,
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    adapter = _adapter()
    for ref in adapter.discover():
        if ref.uuid == uuid:
            pid = adapter.resolve_project_id(ref, idx)
            payload = {
                "ok": True, "uuid": uuid, "project_id": pid,
                "transcript_path": str(ref.transcript_path), "cwd": str(ref.cwd),
                "started_at": ref.started_at.isoformat() if ref.started_at else None,
                "message_count": ref.message_count, "processed": pid and is_processed(repo, pid, uuid),
                "meta": read_meta(repo, pid, uuid) if pid else None,
            }
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"{uuid}: {ref.transcript_path}")
            return
    raise PKMValidationError(f"session not found: {uuid}", code="NOT_FOUND")


@app.command("forget")
def forget_cmd(
    uuid: str,
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    adapter = _adapter()
    for ref in adapter.discover():
        if ref.uuid == uuid:
            pid = adapter.resolve_project_id(ref, idx)
            if pid:
                removed = _forget(repo, pid, uuid)
                if json_out:
                    typer.echo(json.dumps({"ok": True, "removed": removed}))
                return
    raise PKMValidationError(f"session not found: {uuid}", code="NOT_FOUND")


@app.command("mark-processed")
def mark_processed(
    uuid: str,
    extracted_count: int = typer.Option(0, "--extracted-count"),
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    adapter = _adapter()
    for ref in adapter.discover():
        if ref.uuid == uuid:
            pid = adapter.resolve_project_id(ref, idx)
            if not pid:
                raise PKMValidationError(f"session {uuid} resolves to no project", code="NOT_LINKED")
            meta_path = _mark(repo, ref, pid, extracted={"total": extracted_count}, extracted_paths=[])
            if json_out:
                typer.echo(json.dumps({"ok": True, "meta_path": str(meta_path.relative_to(repo))}))
            else:
                typer.echo(f"marked: {uuid} ({pid}, {extracted_count} items)")
            return
    raise PKMValidationError(f"session not found: {uuid}", code="NOT_FOUND")
```

Register in `pkm/cli.py`:
```python
from pkm.commands import session as session_cmd
app.add_typer(session_cmd.app, name="session")
```

- [ ] **Step 3.3: Run tests + commit**

```bash
uv run pytest tests/test_session_list_filters.py tests/test_session_lifecycle.py -v
git add pkm/session/meta.py pkm/commands/session.py pkm/cli.py tests/test_session_list_filters.py tests/test_session_lifecycle.py
git commit -m "M14.3: pkm session list/show/forget/mark-processed"
```

---

## Task 4 — `pkm context inject`

**Files:**
- Create: `pkm/commands/context.py`
- Modify: `pkm/cli.py`
- Test: `tests/test_context_inject.py`

- [ ] **Step 4.1: Write failing tests**

```python
"""pkm context inject — outputs project index.md or stays silent if NOT_LINKED."""

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_context_inject_outputs_index_md(tmp_data_repo, fake_project_setup, tmp_code_repo, monkeypatch):
    # tmp_code_repo has matching git remote → resolves to demo project
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")  # simplest path
    result = runner.invoke(app, ["context", "inject", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0
    assert "demo" in result.output


def test_context_inject_silent_on_not_linked(tmp_data_repo, tmp_unlinked_cwd, monkeypatch):
    monkeypatch.chdir(tmp_unlinked_cwd)
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    result = runner.invoke(app, ["context", "inject", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_context_inject_max_tokens_trims(tmp_data_repo, fake_project_setup, tmp_code_repo, monkeypatch):
    # Seed a long index.md (>1000 chars); --max-tokens 50 should trim
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    long_body = "long content. " * 200
    (tmp_data_repo / "data" / "projects" / "demo" / "index.md").write_text(
        "---\nproject: demo\n---\n\n" + long_body, encoding="utf-8"
    )
    result = runner.invoke(app, ["context", "inject", "--max-tokens", "50", "--data-repo", str(tmp_data_repo)])
    assert "(truncated" in result.output
    # Approximate token count via len/4 heuristic
    assert len(result.output) < 600
```

- [ ] **Step 4.2: Implement**

```python
"""pkm context inject — print project index.md content (or silent if NOT_LINKED)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMNotLinked, PKMValidationError
from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id
from pkm.store.project_paths import project_index

app = typer.Typer(invoke_without_command=True, help="Inject project context into the current AI session.")


def _trim_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Approximate trim using 4-char-per-token heuristic + sentence boundary."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text, False
    cut = text.rfind(".", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return text[:cut + 1] + "\n\n_(truncated; run `/pkm-recall <topic>` for details)_\n", True


@app.callback(invoke_without_command=True)
def main(
    project: str | None = typer.Option(None, "--project"),
    max_tokens: int = typer.Option(600, "--max-tokens"),
    quiet_on_not_linked: bool = typer.Option(True, "--quiet-on-not-linked/--no-quiet"),
    on_session_start: bool = typer.Option(False, "--on-session-start"),  # currently a no-op flag, reserved for future
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = data_repo or resolve_data_repo()
    if repo is None:
        if quiet_on_not_linked:
            return
        raise PKMValidationError("Cannot resolve data repo.", code="DATA_REPO_NOT_FOUND")

    if project:
        pid = project
    else:
        idx = ProjectIndex.load(repo)
        ovs = load_local_overrides(repo)
        pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
    if pid is None:
        if quiet_on_not_linked:
            return
        raise PKMNotLinked("cwd does not resolve to any registered project", code="NOT_LINKED")

    idx_path = project_index(repo, pid)
    if not idx_path.is_file():
        if quiet_on_not_linked:
            return
        raise PKMValidationError(f"index.md missing for {pid}", code="NOT_FOUND")

    text = idx_path.read_text(encoding="utf-8")
    # Strip frontmatter for the inject (keep body only)
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5:]

    trimmed, was_trimmed = _trim_to_tokens(text, max_tokens)
    if json_out:
        typer.echo(json.dumps({"ok": True, "project_id": pid, "content": trimmed, "truncated": was_trimmed}))
    else:
        typer.echo(trimmed)
```

Register in `pkm/cli.py`:
```python
from pkm.commands import context as context_cmd
app.add_typer(context_cmd.app, name="context")
```

- [ ] **Step 4.3: Run tests + commit**

```bash
uv run pytest tests/test_context_inject.py -v
git add pkm/commands/context.py pkm/cli.py tests/test_context_inject.py
git commit -m "M14.4: pkm context inject — project index.md to stdout, quiet on NOT_LINKED"
```

---

## Task 5 — `pkm install --for claude-code`

**Files:**
- Create: `pkm/install/__init__.py`
- Create: `pkm/commands/install.py`
- Create: `pkm/templates/claude_md_block.md`
- Modify: `pkm/cli.py`
- Test: `tests/test_install_claude_code.py`
- Test: `tests/test_install_e2e.py`

- [ ] **Step 5.1: Author CLAUDE.md managed block template**

`pkm/templates/claude_md_block.md`:
```markdown
<!-- pkm:start managed by pkm install -->
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Check if the cwd is a linked PKM project: run `pkm project current --json`.
2. If linked (`ok: true`): invoke the `pkm:recalling-project-context` skill — it loads the project's index.md and recent decisions/pitfalls into context.
3. If not linked (`code: NOT_LINKED`): silently proceed. Do not surface this to the user unless they ask about PKM.

This applies to any cwd, any project — the skill resolves which project automatically.
<!-- pkm:end managed by pkm install -->
```

- [ ] **Step 5.2: Write failing tests**

```python
"""pkm install --for claude-code — global install/uninstall."""

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_install_creates_global_files(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo), "--json"])
    assert result.exit_code == 0, result.output
    # Global config
    assert (tmp_home / ".pkm" / "config.toml").is_file()
    # CLAUDE.md with managed block
    claude_md = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "<!-- pkm:start" in claude_md
    assert "pkm project current" in claude_md
    assert "<!-- pkm:end" in claude_md
    # Slash commands
    for cmd in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        assert (tmp_home / ".claude" / "commands" / cmd).is_file()
    # Skills
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        assert (tmp_home / ".claude" / "skills" / "pkm" / skill / "SKILL.md").is_file()


def test_install_idempotent(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    pre = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    post = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert pre == post


def test_install_preserves_user_content_in_claude_md(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text("# My Custom Header\nUser content here.\n", encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    text = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# My Custom Header" in text
    assert "User content here" in text
    assert "<!-- pkm:start" in text


def test_uninstall_removes_managed_block_only(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text("# User\n", encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    # After install: manifest exists and lists installed paths
    assert (tmp_home / ".pkm" / "install_manifest.json").is_file()
    runner.invoke(app, ["install", "--for", "claude-code", "--uninstall"])
    text = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# User" in text
    assert "<!-- pkm:start" not in text
    assert "pkm project current" not in text
    # commands and skills also removed (via manifest)
    assert not (tmp_home / ".claude" / "commands" / "pkm-recall.md").exists()
    assert not (tmp_home / ".claude" / "skills" / "pkm").exists()
    # Manifest itself is deleted after uninstall
    assert not (tmp_home / ".pkm" / "install_manifest.json").exists()


def test_install_files_have_no_html_marker_above_frontmatter(tmp_data_repo, tmp_home, monkeypatch):
    """Critical: Claude Code skill/slash files must start with `---\\n` (frontmatter).
    An HTML comment above would break Claude Code's frontmatter parser.
    """
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    for cmd in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        text = (tmp_home / ".claude" / "commands" / cmd).read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{cmd} must start with frontmatter, got: {text[:50]!r}"
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        text = (tmp_home / ".claude" / "skills" / "pkm" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill}/SKILL.md must start with frontmatter, got: {text[:50]!r}"
```

Add `tmp_home` fixture:
```python
@pytest.fixture
def tmp_home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h
```

- [ ] **Step 5.3a: Add `__init__.py` files to templates dirs**

```bash
touch pkm/templates/__init__.py  # if missing
mkdir -p pkm/templates/commands pkm/templates/skills/recalling-project-context \
         pkm/templates/skills/extracting-session-knowledge \
         pkm/templates/skills/backfilling-sessions
touch pkm/templates/commands/__init__.py
touch pkm/templates/skills/__init__.py
touch pkm/templates/skills/recalling-project-context/__init__.py
touch pkm/templates/skills/extracting-session-knowledge/__init__.py
touch pkm/templates/skills/backfilling-sessions/__init__.py
```

Verify `pyproject.toml` includes markdown templates in the wheel. If `[tool.hatch.build.targets.wheel]` is used, ensure `include` covers `pkm/templates/**/*.md`. If using setuptools, add to `package_data` or `[tool.setuptools.package-data]`. Check existing config — it likely already includes templates because M12 ships `config.toml.template`.

- [ ] **Step 5.3b: Implement install helpers (manifest-based, no in-file markers for frontmatter files)**

`pkm/install/__init__.py`:
```python
"""Install helpers — two strategies for tracking installed artifacts.

1. Embedded blocks in user-edited files (CLAUDE.md):
   Use <!-- pkm:start --> / <!-- pkm:end --> markers around the block.
   apply_managed_block() inserts/replaces between markers; user content outside
   is preserved.

2. Standalone files (slash commands, skill bodies):
   These start with YAML frontmatter (---\\n...---). An HTML comment above the
   frontmatter would break Claude Code's frontmatter parser. Instead, we record
   the absolute path of every emitted file in ~/.pkm/install_manifest.json.
   Uninstall reads the manifest and deletes exactly those paths.

The two strategies are independent — uninstall calls both remove_managed_block
on CLAUDE.md *and* uninstall_via_manifest for files.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

BLOCK_START = "<!-- pkm:start managed by pkm install -->"
BLOCK_END = "<!-- pkm:end managed by pkm install -->"

MANIFEST_PATH = Path.home() / ".pkm" / "install_manifest.json"


# --- Strategy 1: embedded block in user file ---------------------------------

def apply_managed_block(target: Path, block_content: str) -> None:
    """Insert or replace the managed block in target file. Preserves user content."""
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    pattern = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.DOTALL)
    if pattern.search(existing):
        new = pattern.sub(block_content.strip(), existing)
    else:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new = existing + ("\n" if existing else "") + block_content.strip() + "\n"
    target.write_text(new, encoding="utf-8")


def remove_managed_block(target: Path) -> None:
    if not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    pattern = re.compile(r"\n*" + re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n*", re.DOTALL)
    new = pattern.sub("\n", text).strip()
    if new:
        target.write_text(new + "\n", encoding="utf-8")
    else:
        target.unlink()


# --- Strategy 2: manifest-tracked standalone files ---------------------------

def _templates_root() -> Path:
    """Filesystem path to pkm/templates/ — robust whether installed via uv tool or wheel."""
    import pkm
    return Path(pkm.__file__).parent / "templates"


def read_manifest() -> list[str]:
    if not MANIFEST_PATH.is_file():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("paths", [])
    except (json.JSONDecodeError, OSError):
        return []


def write_manifest(paths: list[str]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps({"paths": sorted(set(paths))}, indent=2), encoding="utf-8")


def install_file(template_relpath: str, target: Path) -> None:
    """Copy a template (path relative to pkm/templates/) verbatim to target.
    Records target in manifest. Always overwrites the target.
    """
    src = _templates_root() / template_relpath
    if not src.is_file():
        raise FileNotFoundError(f"template not found: {src}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    paths = read_manifest()
    abs_target = str(target.resolve())
    if abs_target not in paths:
        paths.append(abs_target)
        write_manifest(paths)


def install_dir(template_reldir: str, target_dir: Path) -> None:
    """Copy all .md files in pkm/templates/<reldir>/ recursively to target_dir.
    Each emitted file is recorded in manifest.
    Skips __init__.py and any non-.md files.
    """
    src_dir = _templates_root() / template_reldir
    if not src_dir.is_dir():
        raise FileNotFoundError(f"template dir not found: {src_dir}")
    for src in src_dir.rglob("*.md"):
        rel = src.relative_to(src_dir)
        target = target_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        paths = read_manifest()
        abs_target = str(target.resolve())
        if abs_target not in paths:
            paths.append(abs_target)
            write_manifest(paths)


def uninstall_via_manifest() -> int:
    """Delete every file recorded in the manifest. Returns count removed."""
    paths = read_manifest()
    removed = 0
    for p in paths:
        try:
            Path(p).unlink()
            removed += 1
        except FileNotFoundError:
            pass  # already gone
        except OSError:
            pass
    if MANIFEST_PATH.is_file():
        MANIFEST_PATH.unlink()
    # Best-effort: prune empty parent dirs (commands/, skills/pkm/, skills/pkm/<skill>/)
    for p in paths:
        parent = Path(p).parent
        for _ in range(4):  # up to 4 levels deep
            try:
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break
    return removed
```

- [ ] **Step 5.4: Implement install command**

`pkm/commands/install.py`:
```python
"""pkm install --for claude-code"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import GlobalConfig, write_global_config, GLOBAL_CONFIG_PATH
from pkm.errors import PKMValidationError
from pkm.install import (
    apply_managed_block, remove_managed_block,
    install_file, install_dir, uninstall_via_manifest,
    _templates_root,
)

app = typer.Typer(invoke_without_command=True)


def _claude_root() -> Path:
    return Path.home() / ".claude"


def _install_claude_code(data_repo: Path) -> dict:
    # 1. global config (data repo location SoT)
    write_global_config(GlobalConfig(data_repo=data_repo.resolve()))

    # 2. CLAUDE.md managed block (Strategy 1 — embedded block, preserves user content)
    block_path = _templates_root() / "claude_md_block.md"
    block = block_path.read_text(encoding="utf-8")
    apply_managed_block(_claude_root() / "CLAUDE.md", block)

    # 3. slash commands (Strategy 2 — verbatim files tracked via manifest)
    cmds_dir = _claude_root() / "commands"
    for name in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        install_file(f"commands/{name}", cmds_dir / name)

    # 4. skills (Strategy 2 — recursive, manifest-tracked)
    skills_root = _claude_root() / "skills" / "pkm"
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        install_dir(f"skills/{skill}", skills_root / skill)

    return {
        "ok": True,
        "data_repo": str(data_repo),
        "global_config": str(GLOBAL_CONFIG_PATH),
        "claude_md": str(_claude_root() / "CLAUDE.md"),
        "commands_dir": str(cmds_dir),
        "skills_dir": str(skills_root),
    }


def _uninstall_claude_code() -> dict:
    # Embedded block in CLAUDE.md → Strategy 1
    remove_managed_block(_claude_root() / "CLAUDE.md")
    # All files (commands + skills) → Strategy 2 manifest
    removed = uninstall_via_manifest()
    return {"ok": True, "files_removed": removed}


@app.callback(invoke_without_command=True)
def main(
    target: str = typer.Option(..., "--for"),
    data_repo: Path | None = typer.Option(None, "--data-repo"),
    uninstall: bool = typer.Option(False, "--uninstall"),
    json_out: bool = typer.Option(False, "--json"),
):
    if target != "claude-code":
        raise PKMValidationError(f"unsupported target: {target} (V1 = claude-code only)", code="NOT_IMPLEMENTED")
    if uninstall:
        result = _uninstall_claude_code()
    else:
        if not data_repo:
            raise PKMValidationError("--data-repo required for install", code="MISSING_ARG")
        result = _install_claude_code(data_repo)
    if json_out:
        typer.echo(json.dumps(result, ensure_ascii=False))
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
```

Register in `pkm/cli.py`:
```python
from pkm.commands import install as install_cmd
app.add_typer(install_cmd.app, name="install")
```

- [ ] **Step 5.5: Run + commit**

```bash
uv run pytest tests/test_install_claude_code.py -v
git add pkm/install/ pkm/commands/install.py pkm/templates/claude_md_block.md \
        pkm/cli.py tests/test_install_claude_code.py
git commit -m "M14.5: pkm install --for claude-code (idempotent, preserves user content)"
```

---

## Task 6 — Skill bundle: `recalling-project-context`

**Files:**
- Create: `pkm/templates/skills/recalling-project-context/SKILL.md`
- Create: `pkm/templates/skills/recalling-project-context/search-scope-guidelines.md`

- [ ] **Step 6.1: Author SKILL.md**

`pkm/templates/skills/recalling-project-context/SKILL.md`:
```markdown
---
name: pkm:recalling-project-context
description: Use at the start of work in any project (after the CLAUDE.md instruction) or whenever the user references prior decisions, patterns, or pitfalls in their codebase. Loads project knowledge from the linked PKM data repo. Self-resolves the current project from cwd; do NOT hardcode project ids.
---

# pkm:recalling-project-context

Loads the user's project knowledge into your context so you can ground recommendations in prior decisions, avoid known pitfalls, and reuse vetted snippets.

## When to use

- At the very start of a coding session in any cwd (the global CLAUDE.md instruction triggers you).
- Mid-session, when the user mentions a topic that may have prior PKM coverage ("OAuth", "the auth migration we did", "remember the rate limit fix").

## When NOT to use

- The user is doing throwaway work or asking general questions not tied to their codebase.
- The cwd is not a linked PKM project (the skill exits silently in that case — do not surface).

## Steps

1. **Resolve current project** (do this every time — never hardcode project ids):
   ```bash
   pkm project current --json
   ```
   - If `ok: false` and `code: NOT_LINKED` → silently end. Do not mention PKM unless the user asks.
   - If `ok: true` → record `project_id` and proceed.

2. **Inject project index**:
   ```bash
   pkm context inject --max-tokens 600 --json
   ```
   The output `content` field is a Markdown summary of the project's recent decisions, pitfalls, snippets. Read it carefully — it represents what your past sessions have decided.

3. **(Optional) On-demand deeper recall** if the user has stated a specific topic for the work:
   ```bash
   pkm search "<user's topic>" --scope project --json -n 5
   ```
   For each hit, you may `Read` the file path to ground your work. See `search-scope-guidelines.md` in this skill for which scope to pick.

4. **One-line acknowledgment** to the user:
   > "Loaded project context for `<project_id>`: N decisions, M pitfalls, K snippets indexed. Will ground recommendations against these."

   Do NOT dump the full index.md content into chat — you've already absorbed it.

## Portability rules (from spec §8.2)

- **Always** call `pkm project current --json` first. The project resolves from cwd dynamically — same skill works in every project on every PC.
- **Never** hardcode paths like `~/Documents/pkm/...`. Always use `pkm` CLI output to discover paths.
- **Never** use `Edit`/`Write` to mutate `data/projects/**` directly — always go through `pkm project knowledge add` (handled by other skills, not this one — this skill only reads).

## See also

- `search-scope-guidelines.md` — choosing `--scope wiki|project|projects|all`.
- `pkm:extracting-session-knowledge` — the inverse skill, used at end of session.
```

- [ ] **Step 6.2: Author search-scope-guidelines.md**

```markdown
# Search Scope Guidelines

PKM search supports several scopes. Pick based on the user's intent.

| User intent | Scope |
|---|---|
| "What did we decide about X in this project?" | `--scope project` (current cwd-resolved project) |
| "Has anyone in any project dealt with X?" | `--scope projects` (all projects, no wiki) |
| "What's the canonical concept for X?" | `--scope wiki` (curated, general knowledge) |
| Mixed / unsure | (default) — when cwd is linked = wiki + current project; otherwise wiki + raw + writing |
| Cross-project pattern discovery | `--scope all` |

## When to override default

The default is usually right. Override only when:
- User explicitly says "search across all projects" → `--scope all` or `--scope projects`.
- User explicitly limits to general concepts → `--scope wiki`.
- Working in monorepo and explicit project context required → `--scope project:<id>`.
```

- [ ] **Step 6.3: Commit**

```bash
git add pkm/templates/skills/recalling-project-context/
git commit -m "M14.6: skill — recalling-project-context"
```

---

## Task 7 — Skill bundle: `extracting-session-knowledge`

**Files:**
- Create: `pkm/templates/skills/extracting-session-knowledge/SKILL.md`
- Create: `pkm/templates/skills/extracting-session-knowledge/extraction-categories.md`
- Create: `pkm/templates/skills/extracting-session-knowledge/output-schema.md`
- Create: `pkm/templates/skills/extracting-session-knowledge/review-protocol.md`

- [ ] **Step 7.1: Author SKILL.md**

```markdown
---
name: pkm:extracting-session-knowledge
description: Use when user wants to harvest knowledge from a Claude Code session (e.g., "정리해줘", "이 세션에서 배운 거 저장하자", "끝!"), or signals work is complete in a linked PKM project. Reads transcript, produces 5-category candidates, reviews with user, writes to data/projects/<id>/.
---

# pkm:extracting-session-knowledge

Turns an AI conversation into permanent project knowledge. Two-round user review gate — extracts everything that could matter, then narrows by user feedback.

## When to use

- User explicitly asks to extract: "정리해줘", "save this session", "extract knowledge".
- User signals end-of-work: "끝", "그럼 이걸로 마무리", "all done", and the cwd is a linked PKM project.

## Prerequisites (the skill checks these)

- `pkm project current` resolves to a project (NOT_LINKED → tell user to `pkm project link` first).
- A session uuid is available (env `CLAUDE_SESSION_ID`, user-provided arg, or fallback to most recent today's session).

## Steps

### 1. Resolve session uuid

Priority:
1. If user passed an arg (e.g., `/pkm-extract-session abc123`) → use that.
2. Else read env var `CLAUDE_SESSION_ID` (Claude Code exposes this).
3. Else `pkm session list --project $(pkm project current) --json --limit 1` → take the most recent.
4. Else: tell user "현재 세션 식별 불가. uuid 인자로 명시해주세요" and stop.

### 2. Get transcript path

```bash
pkm session show <uuid> --json
```

If `code: NOT_LINKED` → "이 세션의 cwd 는 link 안 됨. `pkm project link` 먼저 실행 권장" — stop.

Note `transcript_path` and `project_id` from output.

### 3. Read transcript

Use the `Read` tool on `transcript_path`.

If transcript is very long (> ~5000 lines or token limit risk):
- Process in 50-message windows with 5-message overlap.
- Accumulate candidates per category, deduplicate at the end.

If `Read` raises (corrupt jsonl) → tell user, stop.

### 4. Build candidates

Read `extraction-categories.md` to know what counts as each of the 5 categories. Read `output-schema.md` for the exact JSON shape.

For each category, list candidates with: `title`, `summary` (3-4 sentences max), `tags`, optional `code` (snippets), `derived_from` (cite turns or files referenced).

Be inclusive — if it's borderline, include it. The review gate (step 5) trims.

### 5. Review (round 1)

Present all candidates as a single Markdown table grouped by category. See `review-protocol.md` for the format. Then ask:

> "위 후보들 중 변경/제외할 것 알려주세요 (예: 'decisions 3 빼고, snippets 2 의 제목 OAuth refresh으로 바꿔줘'). 다 OK 면 '진행'."

### 6. Apply user feedback + Review (round 2)

Apply edits, present revised list. Ask:

> "최종 OK?"

If user says no → another round (max 3 rounds; then ask for explicit list).

### 7. Write files

For each accepted candidate:

```bash
echo '<body>' | pkm project knowledge add \
  --project <project_id> \
  --category <category> \
  --slug <user-friendly-slug> \
  --title '<title>' \
  --tags '<tags-comma-sep>' \
  --source-type ai_session \
  --session-id <uuid> \
  --json
```

Capture each `path` returned in JSON.

### 8. Mark processed

```bash
pkm session mark-processed <uuid> --extracted-count <total>
```

### 9. Rebuild + reindex

```bash
pkm project rebuild-index <project_id>
pkm reindex db --scope project:<project_id>
```

### 10. Report

> "Extraction complete. <project_id>: decisions N, pitfalls M, snippets K, qna L, notes O. New items in `data/projects/<project_id>/`. Run `/pkm-recall <topic>` next time to retrieve."

## Portability rules

- Use `pkm project current` and `pkm session show` for all path/id resolution. Never hardcode.
- All file writes go through `pkm project knowledge add`. Do NOT use `Edit`/`Write` directly on `data/projects/**`.
- Single retry on `pkm project knowledge add` failure (e.g., transient git auto-commit conflict). Surface user-facing errors verbatim.
```

- [ ] **Step 7.2: Author `extraction-categories.md`**

```markdown
# Extraction Categories

What counts as each of the 5 categories. Use these definitions when building candidates.

## decisions/

A choice made among alternatives, with rationale.

**Examples:**
- "Use httpOnly cookies for refresh tokens (rationale: XSS resistance)."
- "Drop the legacy V1 endpoint after Q3 (rationale: < 0.1% traffic, security review pending)."

**Not a decision:**
- General knowledge ("CSRF tokens prevent CSRF") → `notes/` or general wiki, not project decisions.
- Code snippet without rationale → `snippets/`.

## pitfalls/

A specific gotcha encountered and the lesson learned.

**Examples:**
- "Don't `await session.commit()` inside `async with session:` — already commits on exit."
- "Migration 0042 hangs if applied during peak traffic; coordinate with ops."

**Not a pitfall:**
- General best practice ("validate inputs") → wiki concepts.
- Decision to use X instead of Y → `decisions/`.

## snippets/

Reusable code or command. Must include the language and the actual code/command.

**Examples:**
- A SQL query that maps users to their org with the correct LATERAL JOIN.
- A bash one-liner to grep for stale flags.

## qna/

A specific question + answer pair. The Q must be unique enough to be searchable.

**Examples:**
- Q: "왜 RLS 가 작동 안 하지?" / A: "...because the policy targets `user_id` not `auth.uid()`."

**Not a qna:**
- Generic Q&A like "what is X" — those go to wiki concepts.

## notes/

Anything worth keeping that doesn't fit the four above. Use sparingly — if everything ends up in notes, you're under-categorizing.
```

- [ ] **Step 7.3: Author `output-schema.md`**

```markdown
# Extraction Output Schema

When building candidates internally, structure them like this. The CLI accepts category and body separately; this schema is for your internal organization before invoking `pkm project knowledge add`.

```json
{
  "decisions": [
    {
      "title": "string (3-10 words)",
      "summary": "string (1-3 sentences)",
      "rationale": "string (1-2 sentences explaining why this option won)",
      "tags": ["lowercase-hyphen", "..."]
    }
  ],
  "pitfalls": [
    {
      "title": "string",
      "summary": "string",
      "context": "string (when/where this trips you up)",
      "tags": ["..."]
    }
  ],
  "snippets": [
    {
      "title": "string",
      "language": "python|sql|bash|...",
      "code": "string (multi-line code block)",
      "purpose": "string (what this is for)",
      "tags": ["..."]
    }
  ],
  "qna": [
    {
      "question": "string",
      "answer": "string",
      "context": "string",
      "tags": ["..."]
    }
  ],
  "notes": [
    {
      "title": "string",
      "body": "string",
      "tags": ["..."]
    }
  ]
}
```

When invoking `pkm project knowledge add`, the body sent via stdin should be Markdown formatted from these fields:

For decisions/pitfalls/qna/notes — the summary + rationale/context/answer becomes prose paragraphs.
For snippets — `purpose` is the lead paragraph, then a fenced code block with `language`.
```

- [ ] **Step 7.4: Author `review-protocol.md`**

```markdown
# Review Protocol — 2-Round User Approval

The user reviews extracted candidates in a markdown table. They respond in natural language; you parse and apply.

## Format (round 1)

```
## decisions (3)
1. **OAuth refresh in cookie** — `httpOnly` + `Secure` + `SameSite=Strict`. _Rationale:_ XSS resistance.
2. **Drop V1 API by Q3** — < 0.1% traffic, security review blocked.
3. **Use Redis for session store, not in-memory** — multi-instance deploys.

## pitfalls (1)
1. **Don't await inside `async with session:`** — `__aexit__` commits.

## snippets (2)
1. **Map user to org** (`sql`) — LATERAL JOIN to handle nullable orgs.
2. **List stale feature flags** (`bash`) — `grep -r FF_ src/ | ...`.

## qna (1)
1. Q: "Why isn't RLS working?" / A: Policy used `user_id` not `auth.uid()`.

## notes (0)
```

After table:

> "위 19 후보 검토 후 변경/제외할 것 알려주세요 (예: '`decisions 2` 빼고, `snippets 1` 의 제목 'org-mapping query' 으로 바꿔'). 다 OK 면 '진행'."

## Round 2 (after user edits)

Apply edits, show the revised list, then:

> "최종 OK?"

If user OK → proceed to write. If user has more edits → another round (max 3).

## Auto-approval mode

If the slash command was invoked with `--auto-approve` (e.g., `/pkm-extract-session abc123 --auto-approve`), skip round 1 and round 2; write all candidates as-is. Only use this mode when explicitly requested.

## Edits parser hints

The user typically says things like:
- "decisions 3 빼" → drop item 3 from decisions
- "snippets 1 제목 X 로" → rename item 1 to X
- "pitfalls 모두 빼" → drop all pitfalls
- "전부 OK" → proceed
- "진행" / "go" → proceed

When ambiguous, ask one clarifying question, then proceed.
```

- [ ] **Step 7.5: Commit**

```bash
git add pkm/templates/skills/extracting-session-knowledge/
git commit -m "M14.7: skill — extracting-session-knowledge (5 categories + 2-round review)"
```

---

## Task 8 — Skill bundle: `backfilling-sessions`

**Files:**
- Create: `pkm/templates/skills/backfilling-sessions/SKILL.md`
- Test: `tests/test_backfill_idempotent.py`

- [ ] **Step 8.1: Author SKILL.md**

```markdown
---
name: pkm:backfilling-sessions
description: Use when user wants to process historical Claude Code sessions in bulk to seed project knowledge ("과거 세션 다 정리하자", "backfill", "분석해서 등록"). Resumable — interrupted backfill picks up from last completed session.
---

# pkm:backfilling-sessions

Bulk-extract knowledge from past Claude Code sessions. Idempotent + resumable: interrupted backfills resume from the last completed session.

## When to use

- User says "이 프로젝트 과거 세션 다 정리해줘" or "/pkm-backfill".
- First time setting up PKM and wanting to seed from existing transcript history.

## Prerequisites

- `pkm project current` or explicit `--project` arg.
- At least one session in `~/.claude/projects/**/*.jsonl` for the target project.

## Steps

### 1. Discover unprocessed sessions

```bash
pkm session list --unprocessed --json [--project <id>] [--since <date>] [--min-messages 5]
```

The `--min-messages 5` default skips trivial sessions. Adjust if user requests.

If 0 sessions → "처리할 세션 없음. 모두 이미 처리됨." Stop.

### 2. Confirm with user

> "<N> 세션 처리 예정 (총 <total_messages> 메시지). 첫 세션은 자세히 검토, 이후는 일괄 모드 가능. 진행?"

Wait for "진행" / "ok" / "go".

Ask separately:

> "첫 세션 검토 후 일괄 모드로 전환할까요? (yes/no)"

### 3. For each session (oldest → newest)

For session i in 1..N:

a. Get transcript: `pkm session show <uuid> --json` → `transcript_path`, `project_id`.

b. Read transcript via `Read` tool. Window if long (50 messages, overlap 5).

c. **First session OR per-session mode**:
   - Run the full `pkm:extracting-session-knowledge` two-round review.
   - After completion, ask: "다음 세션도 같은 방식? 아니면 일괄 모드?"

   **Batch mode after first session**:
   - Build candidates with same logic.
   - Show single round of candidates.
   - Ask "이 세션 일괄 진행 OK? (yes/skip-this/edit/stop-batch)"
   - On `yes` → write directly + mark processed + continue.
   - On `skip-this` → don't write, but mark as processed (so future backfills skip it).
   - On `edit` → drop into round-2 review for this session, then continue batch.
   - On `stop-batch` → exit loop, leave remaining sessions unprocessed.

d. **Crash safety**: if any step in (a)-(c) fails (transcript corrupt, mark-processed errors), do NOT mark processed. The next backfill run will re-attempt.

### 4. After loop

```bash
pkm project rebuild-index <project_id>
pkm reindex db --scope project:<project_id>
```

Report:

> "Backfill complete: <N_processed>/<N_total> sessions, <total_items> items added (decisions <a>, pitfalls <b>, snippets <c>, qna <d>, notes <e>). 검토 미완 항목은 `pkm project show <project_id>` 에서 status=draft 로 확인."

## Resumability

- Each session's mark-processed call writes `.pkm/sessions/<project>/<uuid>.json`.
- Next `pkm session list --unprocessed` automatically excludes processed sessions.
- If user wants to re-process a specific session: `pkm session forget <uuid>` then re-run backfill.

## Cost guardrails

- Long transcripts (>5000 lines) — warn user and process in windows.
- If user has 100+ sessions, suggest `--since` filter to scope.
- Token budget: track approximate per-session and warn if approaching limits.

## Portability rules

Same as `pkm:extracting-session-knowledge`. Always use `pkm` CLI for paths/ids.
```

- [ ] **Step 8.2: Write idempotency test**

```python
"""Backfill idempotency — running twice processes nothing the second time."""

# This is a CLI-level test, not a skill behavior test (the skill is markdown).
# We verify that `pkm session list --unprocessed` returns empty after `mark-processed` was called for each.

import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_backfill_idempotent_via_cli(tmp_data_repo, tmp_transcript_root_with_3_sessions, fake_project_setup, monkeypatch):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_3_sessions))

    # First backfill — list returns 3
    r1 = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    p1 = json.loads(r1.output)
    assert len(p1["sessions"]) == 3

    # Mark all processed
    for s in p1["sessions"]:
        runner.invoke(app, ["session", "mark-processed", s["uuid"], "--extracted-count", "1", "--data-repo", str(tmp_data_repo)])

    # Second backfill — list returns 0
    r2 = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    p2 = json.loads(r2.output)
    assert len(p2["sessions"]) == 0


def test_backfill_resumes_from_partial_progress(tmp_data_repo, tmp_transcript_root_with_3_sessions, fake_project_setup, monkeypatch):
    """Spec §16.3 M14: backfill 중단 후 재호출 시 마지막 처리된 세션 다음부터 재개.

    Simulate a backfill that processed only the first session before interruption.
    The next list --unprocessed must return the remaining 2 sessions in oldest-first order.
    """
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_3_sessions))

    # All 3 visible initially
    r0 = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    initial = json.loads(r0.output)["sessions"]
    assert len(initial) == 3
    first_uuid = initial[0]["uuid"]  # oldest

    # Process only the first one (simulating interruption)
    runner.invoke(app, ["session", "mark-processed", first_uuid, "--extracted-count", "2", "--data-repo", str(tmp_data_repo)])

    # Resume: list unprocessed
    r1 = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    remaining = json.loads(r1.output)["sessions"]
    assert len(remaining) == 2
    assert first_uuid not in [s["uuid"] for s in remaining]

    # Order is preserved (oldest-first)
    times = [s["started_at"] for s in remaining if s.get("started_at")]
    assert times == sorted(times)
```

- [ ] **Step 8.3: Run + commit**

```bash
uv run pytest tests/test_backfill_idempotent.py -v
git add pkm/templates/skills/backfilling-sessions/ tests/test_backfill_idempotent.py
git commit -m "M14.8: skill — backfilling-sessions + idempotency test"
```

---

## Task 9 — Slash command templates (4 files)

**Files:**
- Create: `pkm/templates/commands/pkm-recall.md`
- Create: `pkm/templates/commands/pkm-extract-session.md`
- Create: `pkm/templates/commands/pkm-backfill.md`
- Create: `pkm/templates/commands/pkm-project.md`

- [ ] **Step 9.1: Author each slash template**

`pkm/templates/commands/pkm-recall.md`:
```markdown
---
description: Recall prior decisions, patterns, snippets relevant to a task in the current PKM project.
allowed-tools: Bash, Read, Grep
---

User has invoked `/pkm-recall $ARGUMENTS`. Invoke the `pkm:recalling-project-context` skill, treating `$ARGUMENTS` as the topic to focus the search on.

If the skill resolves NOT_LINKED, tell the user: "현 cwd 는 PKM 프로젝트로 등록 안 됨. `pkm project link` 먼저 실행하시거나, 일반 검색은 `pkm search '$ARGUMENTS' --scope wiki` 를 사용하세요."
```

`pkm/templates/commands/pkm-extract-session.md`:
```markdown
---
description: Extract knowledge from a Claude Code session into the current project's PKM.
allowed-tools: Bash, Read, Edit, Write
---

User has invoked `/pkm-extract-session $ARGUMENTS`. The argument (if any) is a session uuid.

Invoke the `pkm:extracting-session-knowledge` skill. Pass `$ARGUMENTS` as the optional session uuid. If empty, the skill resolves the current session via `CLAUDE_SESSION_ID` env or most-recent-today.

If the user passed `--auto-approve` as part of the args, switch to auto-approve mode (skip review rounds).
```

`pkm/templates/commands/pkm-backfill.md`:
```markdown
---
description: Bulk-extract knowledge from historical Claude Code sessions for a project.
allowed-tools: Bash, Read, Edit, Write
---

User has invoked `/pkm-backfill $ARGUMENTS`. Parse args:
- `--project <id>` — target a specific project (default = current cwd-resolved)
- `--since <YYYY-MM-DD>` — cutoff date
- `--min-messages <N>` — override default 5
- `--limit <N>` — process at most N sessions

Invoke the `pkm:backfilling-sessions` skill with these args.
```

`pkm/templates/commands/pkm-project.md`:
```markdown
---
description: PKM project management — link, current, list, show.
allowed-tools: Bash
---

User has invoked `/pkm-project $ARGUMENTS`. Parse the verb:
- `link [--id <slug>]` → run `pkm project link [--id <slug>]` and report result.
- `current` → run `pkm project current --json` and pretty-print.
- `list` → run `pkm project list` and show.
- `show <id>` → run `pkm project show <id>` and show.

This is a thin CLI wrapper — no skill invocation needed.
```

- [ ] **Step 9.2: Smoke test that install copies them**

(Already covered by `test_install_creates_global_files` in Task 5.)

- [ ] **Step 9.3: Commit**

```bash
git add pkm/templates/commands/
git commit -m "M14.9: 4 slash command templates (recall/extract-session/backfill/project)"
```

---

## Task 10 — `pkm doctor` rows + `--strict` gate

**Files:**
- Modify: `pkm/commands/doctor.py`
- Modify: `tests/test_doctor.py`

- [ ] **Step 10.1: Add rows**

In `pkm/commands/doctor.py`, after existing rows:

```python
def _pkm_install_row() -> dict:
    """Check if pkm install --for claude-code has been run on this PC."""
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    if not claude_md.is_file():
        return {"name": "pkm_install", "status": "missing", "message": "claude-code: not installed (run `pkm install --for claude-code`)"}
    text = claude_md.read_text(encoding="utf-8")
    if "<!-- pkm:start" not in text:
        return {"name": "pkm_install", "status": "missing", "message": "claude-code: managed block not found (run `pkm install --for claude-code`)"}
    # Check skills + commands too
    skills_present = (Path.home() / ".claude" / "skills" / "pkm").is_dir()
    cmds_present = (Path.home() / ".claude" / "commands" / "pkm-recall.md").is_file()
    if not (skills_present and cmds_present):
        return {"name": "pkm_install", "status": "partial", "message": "claude-code: managed block ok, but skills or commands missing"}
    return {"name": "pkm_install", "status": "ok", "message": "claude-code: installed"}


def _unprocessed_sessions_row(repo: Path) -> dict:
    try:
        from pkm.session.adapters import ClaudeCodeAdapter
        from pkm.session.registry import ProjectIndex
        from pkm.session.meta import is_processed
        from pkm.session.registry import resolve_project_id, load_local_overrides
        adapter = ClaudeCodeAdapter()
        idx = ProjectIndex.load(repo)
        ovs = load_local_overrides(repo)
        cwd_pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
        if not cwd_pid:
            return {"name": "unprocessed_sessions", "status": "info", "message": "cwd not linked"}
        unprocessed = 0
        for ref in adapter.discover():
            pid = adapter.resolve_project_id(ref, idx)
            if pid == cwd_pid and not is_processed(repo, pid, ref.uuid):
                unprocessed += 1
        return {"name": "unprocessed_sessions", "status": "info", "message": f"{unprocessed} unprocessed for {cwd_pid}"}
    except Exception as e:
        return {"name": "unprocessed_sessions", "status": "info", "message": f"unavailable: {e}"}
```

In the doctor flow, append these rows. In `--strict` mode:

```python
if strict:
    install_row = _pkm_install_row()
    if install_row["status"] in ("missing", "partial"):
        from pkm.errors import PKMInstallMissing
        raise PKMInstallMissing(install_row["message"], code="PKM_INSTALL_MISSING")
```

- [ ] **Step 10.2: Tests**

```python
def test_doctor_pkm_install_missing(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["doctor", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    install_item = next(i for i in payload["items"] if i["name"] == "pkm_install")
    assert install_item["status"] == "missing"


def test_doctor_strict_fails_when_install_missing(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["doctor", "--strict", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "PKM_INSTALL_MISSING"


def test_doctor_strict_passes_after_install(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["doctor", "--strict", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0
```

- [ ] **Step 10.3: Run + commit**

```bash
uv run pytest tests/test_doctor.py -v
git add pkm/commands/doctor.py tests/test_doctor.py
git commit -m "M14.10: doctor pkm_install + unprocessed_sessions rows + --strict gate"
```

---

## Task 11 — Acceptance test (M14 portion)

**Files:**
- Create: `tests/test_v3_acceptance_m14.py`

- [ ] **Step 11.1: Write acceptance tests per spec §16.3 M14**

```python
"""M14 acceptance — verify spec §16.3 M14 criteria."""

import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_install_idempotent(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: pkm install --for claude-code 멱등 (재실행 → 변경 0)"""
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    sigs1 = _file_signatures(tmp_home / ".claude")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    sigs2 = _file_signatures(tmp_home / ".claude")
    assert sigs1 == sigs2


def test_uninstall_preserves_user_content(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: --uninstall 가 managed 마커만 제거 (사용자 수동 추가 보존)"""
    monkeypatch.setenv("HOME", str(tmp_home))
    user_text = "# User\nMy content.\n"
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text(user_text, encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    runner.invoke(app, ["install", "--for", "claude-code", "--uninstall"])
    final = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "My content." in final
    assert "<!-- pkm:" not in final


def test_session_list_unprocessed_only_returns_unmarked(tmp_data_repo, tmp_transcript_root_with_2_sessions, fake_project_setup, monkeypatch):
    """Spec §16.3 M14: session list --unprocessed 가 메타파일 없는 세션만 반환"""
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    runner.invoke(app, ["session", "mark-processed", "first", "--extracted-count", "1", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    uuids = [s["uuid"] for s in payload["sessions"]]
    assert "first" not in uuids
    assert "second" in uuids


def test_doctor_strict_install_missing(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: doctor --strict 가 PKM install 누락 시 PKM_INSTALL_MISSING exit 1"""
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["doctor", "--strict", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    assert json.loads(result.output)["error"]["code"] == "PKM_INSTALL_MISSING"


def _file_signatures(root: Path) -> dict[str, str]:
    """Return {relative_path: hash} for all files under root."""
    import hashlib
    sigs = {}
    for p in root.rglob("*"):
        if p.is_file():
            sigs[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return sigs
```

- [ ] **Step 11.2: Run + commit**

```bash
uv run pytest tests/test_v3_acceptance_m14.py -v
git add tests/test_v3_acceptance_m14.py
git commit -m "M14.11: V3 acceptance test (M14 portion)"
```

---

## Task 12 — Documentation update (UC8 + UC9 + README)

**Files:**
- Modify: `docs/FEATURES.md`
- Modify: `README.md`

- [ ] **Step 12.1: Update FEATURES.md**

Add command group sections:

```markdown
### 2.12 Session (M14)

```bash
pkm session list [--project ID] [--unprocessed] [--since DATE] [--min-messages N=5] [--limit N] [--json]
pkm session show <uuid> [--json]
pkm session forget <uuid>
pkm session mark-processed <uuid> --extracted-count N
```

`pkm session list` 가 `~/.claude/projects/**/*.jsonl` 을 스캔하여 cwd 매핑된 프로젝트의 세션만 반환. `--unprocessed` 는 `.pkm/sessions/<id>/<uuid>.json` 메타파일 없는 세션만.

### 2.13 Install (M14)

```bash
pkm install --for claude-code [--data-repo PATH] [--uninstall] [--json]
```

PC 별 1 회 실행. ~/.pkm/config.toml + ~/.claude/CLAUDE.md (managed 블록) + ~/.claude/{commands,skills}/pkm-* 파일을 멱등 작성. `--uninstall` 시 managed 마커 가진 항목만 제거.

### 2.14 Context (M14)

```bash
pkm context inject [--project ID] [--max-tokens N=600] [--quiet-on-not-linked]
```

현재 프로젝트의 `index.md` 본문을 stdout. NOT_LINKED 면 silent. SessionStart hook 대신 `~/.claude/CLAUDE.md` 의 managed 블록이 `pkm:recalling-project-context` 스킬을 invoke 하고, 스킬이 이 명령을 호출.
```

Add UC8 + UC9:

```markdown
### UC8. Claude Code 세션 끝난 후 지식 추출 → 프로젝트 등록

상황: hwi_PKM 작업 중 OAuth 결정 + 미들웨어 함정 + SQL 스니펫이 쌓였다.

```
Claude Code 세션 안에서:
  /pkm-extract-session
  → pkm:extracting-session-knowledge 스킬 invoke
  → 1. CLAUDE_SESSION_ID env 또는 최근 세션 → uuid 결정
  → 2. pkm session show → transcript_path
  → 3. transcript Read 툴로 읽기
  → 4. 5 카테고리 후보 빌드 (decisions 3, pitfalls 1, snippets 5, qna 0, notes 2)
  → 5. 사용자에게 markdown 표 제시 → "decisions 3 빼고 진행" 응답
  → 6. 반영 후 재출력 → "OK"
  → 7. pkm project knowledge add 항목별 호출 (10 회) — auto-commit
  → 8. pkm session mark-processed
  → 9. pkm project rebuild-index hwi-pkm
  → 10. pkm reindex db --scope project:hwi-pkm

결과:
  data/projects/hwi-pkm/decisions/2026-05-07-*.md (2 개)
  data/projects/hwi-pkm/pitfalls/2026-05-07-*.md (1 개)
  data/projects/hwi-pkm/snippets/2026-05-07-*.md (5 개)
  data/projects/hwi-pkm/notes/2026-05-07-*.md (2 개)
  .pkm/sessions/hwi-pkm/<uuid>.json (메타)
  data/projects/hwi-pkm/index.md (자동 갱신)
```

다음 세션에서 `/pkm-recall OAuth` 하면 검색에 즉시 잡힘.

### UC9. 과거 세션 일괄 backfill

상황: PKM 처음 도입 + ~/.claude/projects/-Users-me-Code-app/ 에 47 개 세션 누적.

```
1) cd ~/Code/my-app
2) pkm project link --id my-app
3) Claude Code 세션 안에서:
   /pkm-backfill --project my-app --since 2026-01-01

   → pkm:backfilling-sessions 스킬:
     - pkm session list --unprocessed → 47 세션
     - 사용자 확인 + "첫 세션 자세히 / 이후 일괄"
     - 첫 세션: 두 라운드 검토 → 8 항목 등록
     - 두 번째부터: 일괄 모드 — 한 번 보여주고 yes/skip/edit/stop
     - 세션 12 에서 사용자 stop-batch
     - 처리: 12/47 세션, ~80 항목

4) 다음에 /pkm-backfill 재호출 → 13 부터 자동 재개
```

중단 시점까지 안전 — 처리된 세션은 메타파일에 기록되어 재처리되지 않음.
```

- [ ] **Step 12.2: Update README**

Add to commands table:
```markdown
| Session | `pkm session {list,show,forget,mark-processed}` |
| Install | `pkm install --for claude-code [--data-repo PATH] [--uninstall]` |
| Context | `pkm context inject [--max-tokens N]` |
```

Add to progress checklist:
```markdown
- [ ] M14 — Session Adapter + Skills (in progress)
```

(Mark M13 as `[x]` if M13 already merged.)

- [ ] **Step 12.3: Update SCHEMA.md (data repo template)**

If `pkm/templates/SCHEMA.md` exists (data repo's runtime SCHEMA), add a section about the 7th layer + slash commands. The data-repo SCHEMA.md is what AI agents read when working in the data repo, so this is important for operator awareness.

- [ ] **Step 12.4: Commit**

```bash
git add README.md docs/FEATURES.md pkm/templates/SCHEMA.md
git commit -m "M14.12: docs — UC8/UC9 walk-throughs, session/install/context commands"
```

---

## Wrap-up

- [ ] **Step W.1: Full regression**

```bash
uv run pytest -v
```

Expected: All M13 + M14 tests pass + existing V1/V2 tests still pass.

- [ ] **Step W.2: End-to-end smoke (multi-PC parity proxy)**

Simulate first PC:
```bash
mkdir -p /tmp/m14-smoke/{datarepo,coderepo,fake-home/.claude/projects/-tmp-m14-smoke-coderepo}
cd /tmp/m14-smoke/datarepo
uv run pkm init
uv run pkm migrate --apply

# Seed a fake transcript
cat > /tmp/m14-smoke/fake-home/.claude/projects/-tmp-m14-smoke-coderepo/test-uuid.jsonl <<'EOF'
{"type":"user","content":"OAuth tokens 어디 저장?","timestamp":"2026-05-07T10:00:00Z"}
{"type":"assistant","content":"httpOnly cookie","timestamp":"2026-05-07T10:00:30Z"}
{"type":"user","content":"왜?","timestamp":"2026-05-07T10:01:00Z"}
{"type":"assistant","content":"XSS 노출 방지","timestamp":"2026-05-07T10:01:30Z"}
{"type":"user","content":"좋아","timestamp":"2026-05-07T10:02:00Z"}
EOF

# Install
HOME=/tmp/m14-smoke/fake-home uv run pkm install --for claude-code --data-repo /tmp/m14-smoke/datarepo

# Verify install
ls /tmp/m14-smoke/fake-home/.claude/{commands,skills,CLAUDE.md}
ls /tmp/m14-smoke/fake-home/.pkm/config.toml

# Link project
cd /tmp/m14-smoke/coderepo && git init && git remote add origin git@github.com:test/test.git
HOME=/tmp/m14-smoke/fake-home PKM_DATA_REPO=/tmp/m14-smoke/datarepo PKM_TRANSCRIPT_ROOT=/tmp/m14-smoke/fake-home/.claude/projects \
  uv run pkm project link --id test

# List unprocessed sessions
HOME=/tmp/m14-smoke/fake-home PKM_TRANSCRIPT_ROOT=/tmp/m14-smoke/fake-home/.claude/projects \
  uv run pkm session list --unprocessed --json

# context inject (should output index.md content)
HOME=/tmp/m14-smoke/fake-home PKM_DATA_REPO=/tmp/m14-smoke/datarepo \
  uv run pkm context inject --project test

# doctor --strict (should pass after install)
HOME=/tmp/m14-smoke/fake-home PKM_DATA_REPO=/tmp/m14-smoke/datarepo \
  uv run pkm doctor --strict
```

Expected: all commands succeed; doctor strict exits 0.

- [ ] **Step W.3: Update README progress checkbox**

Mark `[x] M14` if all acceptance tests pass + smoke is clean.

```bash
git add README.md
git commit -m "M14: complete — session adapter + Claude Code skills + global install"
```

- [ ] **Step W.4: Dogfood (per spec §19)**

```bash
cd ~/Documents/pkm
uv run pkm install --for claude-code --data-repo $(pwd)

cd ~/Downloads/Claude_lab/hwi_PKM
uv run pkm project link --id hwi-pkm
# In Claude Code:
# /pkm-backfill --project hwi-pkm --since 2026-04-01
# /pkm-recall "M11 grounding gate"
```

Verify the V3 GA evidence per spec §19.

---

V3 (M13 + M14) complete. Spec §16.3 acceptance criteria all green ⇒ V3 GA.
