"""Pytest scaffolding — memory safety + stub embedder default.

Goals (spec §8.3):
- The fast test suite NEVER loads real ML models. Tests requiring real models
  must be `@pytest.mark.slow`, run sequentially in a separate workflow.
- A runaway test cannot crash the host. We cap virtual address space on
  Unix-like systems. Default 4 GB; override via `PKM_TEST_RSS_CAP_GB`.
- Spec §8.3 + §9.4 cap the fast suite at < 2 min wall-time and ≤ 4 GB RSS.
  M7.4 enforces those as hard gates via `_session_clock` (consumed by
  `tests/test_perf_gate.py`) and `_rss_guard` (autouse below).

xdist note: with `pytest-xdist -n auto`, session-scope fixtures run once
per worker process. So `_session_clock` measures elapsed-time-from-the-
first-test-on-this-worker and `_rss_guard` measures peak-RSS-of-this-
worker. Both are still meaningful: the slowest worker bounds the total
wall-time, and each worker individually must stay under 4 GB. We
deliberately avoid a `pytest_sessionfinish` hook — the added complexity
isn't worth it for an 11s suite.

This conftest runs before any test session — see pytest's discovery order.
"""

from __future__ import annotations

import os
import resource
import subprocess
import time

import psutil
import pytest


def _apply_rss_cap() -> None:
    """Cap process virtual memory to prevent runaway tests from OOMing the host.

    Unix only. Best-effort: we lower the soft limit but never raise it.
    """
    if not hasattr(resource, "RLIMIT_AS"):
        return
    try:
        cap_gb = float(os.environ.get("PKM_TEST_RSS_CAP_GB", "4"))
    except ValueError:
        cap_gb = 4.0
    cap_bytes = int(cap_gb * 1024**3)
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)

    new_soft: int
    if soft == resource.RLIM_INFINITY:
        new_soft = cap_bytes
    else:
        new_soft = min(soft, cap_bytes)

    if hard != resource.RLIM_INFINITY and new_soft > hard:
        new_soft = hard

    try:
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))
    except (ValueError, OSError):
        # Some sandboxed environments refuse setrlimit. Don't crash the suite.
        pass


# Default the stub embedder and reranker ON — real models must be opt-in via slow tests.
os.environ.setdefault("PKM_TEST_STUB_EMBEDDER", "1")
os.environ.setdefault("PKM_TEST_SKIP_DOWNLOAD", "1")
os.environ.setdefault("PKM_TEST_STUB_RERANKER", "1")

_apply_rss_cap()


# RSS gate threshold — §9.4 says ≤ 4 GB.
_RSS_BUDGET_BYTES = 4 * 1024 * 1024 * 1024


class _Clock:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_so_far(self) -> float:
        return time.monotonic() - self._start


@pytest.fixture(scope="session")
def _session_clock() -> _Clock:
    return _Clock()


@pytest.fixture(scope="session", autouse=True)
def _rss_guard():
    """Fail the session if peak RSS of the test process exceeds §9.4's 4 GB.

    Under pytest-xdist, this runs once per worker process — so each worker
    is bounded individually (4 GB per worker, not 4 GB summed across 14
    workers: each worker runs in its own process and only this worker's
    footprint is measured here). If this is misleading on a single-machine
    CI runner, profile with `--show-capture` and drop xdist for diagnosis.
    """
    if os.environ.get("PKM_RSS_GATE_OFF") == "1":
        yield
        return
    proc = psutil.Process(os.getpid())
    peak = proc.memory_info().rss
    yield
    final = proc.memory_info().rss
    peak = max(peak, final)
    assert peak <= _RSS_BUDGET_BYTES, (
        f"peak RSS {peak / (1024**3):.2f} GB exceeded §9.4 budget "
        f"{_RSS_BUDGET_BYTES / (1024**3):.0f} GB"
    )


# ---------------------------------------------------------------------------
# M13 Task 5 fixtures — project command testing
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_repo(tmp_path):
    repo = tmp_path / "datarepo"
    repo.mkdir()
    (repo / "data" / "raw" / "captures").mkdir(parents=True)
    (repo / "data" / "wiki" / "concepts").mkdir(parents=True)
    (repo / "data" / "writing").mkdir(parents=True)
    (repo / "data" / "projects").mkdir(parents=True)
    (repo / ".pkm").mkdir()
    (repo / ".pkm" / "config.toml").write_text("# scaffolded\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def tmp_code_repo(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    return repo


@pytest.fixture
def tmp_code_repo_pair(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    return a, b


# ---------------------------------------------------------------------------
# M13 Task 8 fixtures — project search scope testing
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_indexed_data_repo(tmp_path, monkeypatch):
    """Data repo with 1 wiki + 1 project knowledge file, both indexed."""
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    repo = tmp_path / "indexed-datarepo"
    repo.mkdir()
    for sub in ("data/raw/captures", "data/wiki/concepts", "data/writing", "data/projects"):
        (repo / sub).mkdir(parents=True)
    (repo / ".pkm").mkdir()
    (repo / ".pkm" / "config.toml").write_text("# scaffolded\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)

    # Apply migrations so chunks has project/category/session_id columns
    from typer.testing import CliRunner
    from pkm.cli import app
    runner = CliRunner()
    runner.invoke(app, ["migrate", "--apply", "--root", str(repo)])

    # Seed 1 wiki page
    (repo / "data" / "wiki" / "concepts" / "oauth.md").write_text(
        "---\nslug: oauth\ntitle: OAuth\nbucket: concepts\nstatus: active\n"
        "lang: en\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "updated_at: 2026-05-07T00:00:00+09:00\ntags: []\n---\n\n"
        "OAuth refresh tokens — wiki overview.\n",
        encoding="utf-8",
    )

    # Seed 1 project + 1 knowledge file
    pdir = repo / "data" / "projects" / "demo"
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        (pdir / cat).mkdir(parents=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:test/demo\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n"
        "---\n\n# demo\n",
        encoding="utf-8",
    )
    (pdir / "decisions" / "2026-05-07-oauth-cookie.md").write_text(
        "---\ntitle: OAuth in cookie\nslug: 2026-05-07-oauth-cookie\n"
        "created_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\n"
        "source_type: ai_session\nlang: en\nproject: demo\ncategory: decisions\n"
        "tags: []\n---\n\n"
        "OAuth refresh tokens stored in httpOnly cookies.\n",
        encoding="utf-8",
    )

    # Build index
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(repo)])
    return repo


@pytest.fixture
def tmp_unlinked_cwd(tmp_path):
    """A directory that is NOT a git repo and won't resolve to any project."""
    p = tmp_path / "unlinked-cwd"
    p.mkdir()
    return p


# ---------------------------------------------------------------------------
# M14 Task 2 fixtures — session adapter testing
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_transcript_root(tmp_path):
    """A fake ~/.claude/projects tree with one cwd dir + typical_session.jsonl."""
    import shutil
    from pathlib import Path as _Path
    root = tmp_path / "claude_projects"
    root.mkdir()
    cwd_dir = root / "-Users-me-code-demo"
    cwd_dir.mkdir()
    src = _Path(__file__).parent / "fixtures" / "sessions" / "typical_session.jsonl"
    shutil.copy(str(src), str(cwd_dir / "11111111-2222-3333-4444-555555555555.jsonl"))
    return root


@pytest.fixture
def typical_session_jsonl():
    """Absolute path to tests/fixtures/sessions/typical_session.jsonl."""
    import pathlib
    return pathlib.Path(__file__).parent / "fixtures" / "sessions" / "typical_session.jsonl"


@pytest.fixture
def corrupt_session_jsonl():
    """Absolute path to tests/fixtures/sessions/corrupt_session.jsonl."""
    import pathlib
    return pathlib.Path(__file__).parent / "fixtures" / "sessions" / "corrupt_session.jsonl"


@pytest.fixture
def fake_project_index():
    """A ProjectIndex with one record matching github.com:test/demo."""
    from pkm.session.registry import ProjectIndex, ProjectRecord
    return ProjectIndex(records=[
        ProjectRecord(
            id="demo",
            git_remotes=["github.com:test/demo"],
            local_paths=[],
        )
    ])


# ---------------------------------------------------------------------------
# M14 Task 3 fixtures — session lifecycle + list filters
# ---------------------------------------------------------------------------

import json as _json_session


def _write_synthetic_session(target, n_messages: int) -> None:
    lines = []
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        lines.append(_json_session.dumps({
            "type": role,
            "content": f"message {i} content",
            "timestamp": f"2026-05-07T1{i % 10}:{(i * 7) % 60:02d}:00Z",
        }))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def fake_project_setup(tmp_data_repo, monkeypatch):
    """Seed data/projects/demo/ + stub discover_remote so adapter resolves to demo."""
    pdir = tmp_data_repo / "data" / "projects" / "demo"
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        (pdir / cat).mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:test/test\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n\n# demo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pkm.session.adapters.claude_code.discover_remote",
        lambda cwd: "github.com:test/test",
    )
    return tmp_data_repo


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
    """Three sessions with deterministic uuids 'a', 'b', 'c'."""
    root = tmp_path / "transcripts"
    cwd_dir = root / "-tmp-test-coderepo"
    cwd_dir.mkdir(parents=True)
    for uuid_ in ["a", "b", "c"]:
        _write_synthetic_session(cwd_dir / f"{uuid_}.jsonl", n_messages=6)
    return root


@pytest.fixture
def tmp_unlinked_cwd_m14(tmp_path):
    """A cwd that isn't linked to any project (M14 variant)."""
    p = tmp_path / "unlinked"
    p.mkdir()
    return p


@pytest.fixture
def tmp_home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h
