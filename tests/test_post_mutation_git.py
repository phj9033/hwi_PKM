"""Integration: post_mutation calls commit_paths after log/TOC/reindex."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pkm._mutations import post_mutation
from pkm.store import git as gitmod
from pkm.store.log import LogEvent


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _bare_pkm(tmp_path: Path) -> Path:
    """Scaffold a PKM tree + git repo (so the git step can run)."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "writing").mkdir(parents=True)
    (tmp_path / ".pkm").mkdir(parents=True)
    (tmp_path / "data" / "log.md").write_text("", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("/.pkm/index.db\n", encoding="utf-8")
    gitmod.git_init(tmp_path)
    # Initial commit so HEAD exists
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_post_mutation_returns_commit_sha(tmp_path: Path):
    root = _bare_pkm(tmp_path)
    rel = "data/raw/captures/2026-05-01-foo.md"
    (root / rel).write_text(
        "---\ntitle: foo\nslug: 2026-05-01-foo\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "Body of foo.\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="2026-05-01-foo", message="foo")
    sha = post_mutation(root, event, paths=[rel])
    assert sha is not None
    assert len(sha) == 40

    # Verify the commit message
    out = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=root,
        capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "pkm capture.create: 2026-05-01-foo"


def test_post_mutation_no_git_repo_returns_none_and_warns(tmp_path: Path, capsys):
    """No .git/ → warn to stderr, return None, mutation still succeeds."""
    # Bare scaffold WITHOUT git_init
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True)
    (tmp_path / "data" / "log.md").write_text("", encoding="utf-8")
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "writing").mkdir(parents=True)
    (tmp_path / ".pkm").mkdir(parents=True)

    rel = "data/raw/captures/x.md"
    (tmp_path / rel).write_text(
        "---\ntitle: x\nslug: x\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "body\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="x", message="x")
    sha = post_mutation(tmp_path, event, paths=[rel])
    assert sha is None
    captured = capsys.readouterr()
    assert "not a git repo" in captured.err.lower() or \
           "skipping commit" in captured.err.lower()


def test_post_mutation_commits_log_and_index_too(tmp_path: Path):
    """The commit must include data/log.md and data/index.md, not just the
    explicit paths argument."""
    root = _bare_pkm(tmp_path)
    rel = "data/raw/captures/y.md"
    (root / rel).write_text(
        "---\ntitle: y\nslug: y\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="y", message="y")
    sha = post_mutation(root, event, paths=[rel])
    assert sha is not None

    files = subprocess.run(
        ["git", "show", "--name-only", "--format=", sha],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert rel in files
    assert "data/log.md" in files
    # index.md only present if M2's rebuild_index produced it (it does)
    assert "data/index.md" in files


def test_post_mutation_no_paths_still_commits_log_and_index(tmp_path: Path):
    """A pure log-only event (no file paths) should still produce a commit
    of just the log.md + index.md changes."""
    root = _bare_pkm(tmp_path)
    event = LogEvent(type="manual", ref="r", message="m")
    sha = post_mutation(root, event)  # no paths
    assert sha is not None  # log.md changed → there's something to commit
