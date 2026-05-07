"""Tests for pkm/session/meta.py — mark-processed / forget lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.session.adapters.base import SessionRef
from pkm.session.meta import (
    forget,
    is_processed,
    mark_processed,
    read_meta,
)

runner = CliRunner()


def _make_ref(transcript_path: Path, uuid: str = "test-uuid") -> SessionRef:
    return SessionRef(
        uuid=uuid,
        cwd=Path("/tmp/test"),
        started_at=None,
        last_message_at=None,
        message_count=6,
        model=None,
        transcript_path=transcript_path,
    )


# ---------------------------------------------------------------------------
# test_mark_processed_creates_meta_file
# ---------------------------------------------------------------------------

def test_mark_processed_creates_meta_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","content":"hi"}\n', encoding="utf-8")

    ref = _make_ref(transcript, uuid="abc123")
    meta_path = mark_processed(
        repo, ref, "demo",
        extracted={"total": 3},
        extracted_paths=["data/projects/demo/decisions/2026-05-07-foo.md"],
    )

    assert meta_path.is_file()
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    assert data["session_uuid"] == "abc123"
    assert data["project_id"] == "demo"
    assert data["extracted"]["total"] == 3
    assert data["extracted_paths"] == ["data/projects/demo/decisions/2026-05-07-foo.md"]
    assert "processed_at" in data
    assert "transcript_sha256" in data
    assert data["transcript_message_count"] == 6


# ---------------------------------------------------------------------------
# test_forget_removes_meta_file
# ---------------------------------------------------------------------------

def test_forget_removes_meta_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","content":"hi"}\n', encoding="utf-8")

    ref = _make_ref(transcript, uuid="forget-me")
    mark_processed(repo, ref, "demo", extracted={"total": 1}, extracted_paths=[])

    assert is_processed(repo, "demo", "forget-me")

    removed = forget(repo, "demo", "forget-me")
    assert removed is True
    assert not is_processed(repo, "demo", "forget-me")


# ---------------------------------------------------------------------------
# test_mark_processed_idempotent
# ---------------------------------------------------------------------------

def test_mark_processed_idempotent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","content":"hi"}\n', encoding="utf-8")

    ref = _make_ref(transcript, uuid="idem")
    mark_processed(repo, ref, "demo", extracted={"total": 1}, extracted_paths=[])
    mark_processed(repo, ref, "demo", extracted={"total": 2}, extracted_paths=[])

    # Second call overwrites — file still exists, content reflects last call.
    assert is_processed(repo, "demo", "idem")
    data = read_meta(repo, "demo", "idem")
    assert data is not None
    assert data["extracted"]["total"] == 2


# ---------------------------------------------------------------------------
# test_forget_nonexistent_returns_false
# ---------------------------------------------------------------------------

def test_forget_nonexistent_returns_false(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    removed = forget(repo, "demo", "no-such-uuid")
    assert removed is False


# ---------------------------------------------------------------------------
# test_meta_dir_created_on_mark
# ---------------------------------------------------------------------------

def test_meta_dir_created_on_mark(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","content":"hello"}\n', encoding="utf-8")

    ref = _make_ref(transcript, uuid="dir-test")
    meta_path = mark_processed(repo, ref, "myproject", extracted={}, extracted_paths=[])

    # Directory must exist with the right structure.
    assert (repo / ".pkm" / "sessions" / "myproject").is_dir()
    assert meta_path == repo / ".pkm" / "sessions" / "myproject" / "dir-test.json"


# ---------------------------------------------------------------------------
# test_read_meta_returns_none_when_absent
# ---------------------------------------------------------------------------

def test_read_meta_returns_none_when_absent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = read_meta(repo, "demo", "nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# CLI integration: mark-processed and forget via CliRunner
# ---------------------------------------------------------------------------

def test_cli_mark_processed_creates_meta(fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch):
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "mark-processed", "first", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    assert data["project_id"] == "demo"

    # Meta file must now exist on disk.
    meta_file = repo / ".pkm" / "sessions" / "demo" / "first.json"
    assert meta_file.is_file()


def test_cli_forget_removes_meta(fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch):
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    # First mark, then forget.
    runner.invoke(app, ["session", "mark-processed", "first", "--json"])
    result = runner.invoke(app, ["session", "forget", "first", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    assert data["removed"] is True

    meta_file = repo / ".pkm" / "sessions" / "demo" / "first.json"
    assert not meta_file.is_file()
