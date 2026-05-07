"""Tests for pkm session list/show command filters."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# test_session_list_filters_unprocessed
# ---------------------------------------------------------------------------

def test_session_list_filters_unprocessed(
    fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch
):
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    # Mark "first" as processed.
    runner.invoke(app, ["session", "mark-processed", "first", "--json"])

    # With --unprocessed, only "second" should appear.
    result = runner.invoke(app, ["session", "list", "--unprocessed", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    uuids = [s["uuid"] for s in data["sessions"]]
    assert "first" not in uuids
    assert "second" in uuids


# ---------------------------------------------------------------------------
# test_session_list_min_messages_default
# ---------------------------------------------------------------------------

def test_session_list_min_messages_default(
    fake_project_setup, tmp_path, monkeypatch
):
    """Sessions with < 5 messages are filtered out by default (--min-messages=5)."""
    repo = fake_project_setup
    import sys
    sys.path.insert(0, str(repo.parent.parent))  # ensure pkm is importable

    # Build a custom transcript root with one short (2 msgs) and one long (6 msgs) session.
    root = tmp_path / "transcript_root"
    cwd_dir = root / "-tmp-test-coderepo"
    cwd_dir.mkdir(parents=True)

    # Short session (2 messages — below default min of 5).
    lines_short = [
        json.dumps({"type": "user", "content": "hi", "timestamp": "2026-05-07T10:00:00Z"}),
        json.dumps({"type": "assistant", "content": "hello", "timestamp": "2026-05-07T10:01:00Z"}),
    ]
    (cwd_dir / "short.jsonl").write_text("\n".join(lines_short) + "\n", encoding="utf-8")

    # Long session (6 messages — above default min of 5).
    long_lines = []
    for i in range(6):
        role = "user" if i % 2 == 0 else "assistant"
        long_lines.append(json.dumps({
            "type": role,
            "content": f"msg {i}",
            "timestamp": f"2026-05-07T11:{i * 5:02d}:00Z",
        }))
    (cwd_dir / "long.jsonl").write_text("\n".join(long_lines) + "\n", encoding="utf-8")

    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(root))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    uuids = [s["uuid"] for s in data["sessions"]]
    assert "short" not in uuids, "Short session (2 msgs) must be filtered by default min-messages=5"
    assert "long" in uuids, "Long session (6 msgs) must appear in results"


# ---------------------------------------------------------------------------
# test_session_show_returns_transcript_path
# ---------------------------------------------------------------------------

def test_session_show_returns_transcript_path(
    fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch
):
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "show", "first", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    assert data["uuid"] == "first"
    assert "transcript_path" in data
    assert data["transcript_path"].endswith("first.jsonl")


# ---------------------------------------------------------------------------
# test_session_list_since_filter
# ---------------------------------------------------------------------------

def test_session_list_since_filter(
    fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch
):
    """--since filters out sessions that started before the given ISO timestamp."""
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    # First check what the sessions look like without filter.
    result = runner.invoke(app, ["session", "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True

    # Both sessions start at 2026-05-07T10:00:00+00:00 (first line timestamp).
    # Using --since with a future date should filter everything out.
    result_filtered = runner.invoke(
        app,
        ["session", "list", "--since", "2026-05-08T00:00:00+00:00", "--json"],
    )
    assert result_filtered.exit_code == 0, result_filtered.output
    data_filtered = json.loads(result_filtered.output.strip())
    assert data_filtered["ok"] is True
    # All sessions started before 2026-05-08, so none should pass the since filter.
    assert len(data_filtered["sessions"]) == 0


# ---------------------------------------------------------------------------
# test_session_list_project_filter
# ---------------------------------------------------------------------------

def test_session_list_project_filter(
    fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch
):
    """--project=demo returns sessions; --project=other returns none."""
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "list", "--project", "demo", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    assert len(data["sessions"]) >= 1
    for s in data["sessions"]:
        assert s["project_id"] == "demo"

    result_other = runner.invoke(app, ["session", "list", "--project", "other", "--json"])
    assert result_other.exit_code == 0, result_other.output
    data_other = json.loads(result_other.output.strip())
    assert data_other["ok"] is True
    assert len(data_other["sessions"]) == 0


# ---------------------------------------------------------------------------
# test_session_list_limit
# ---------------------------------------------------------------------------

def test_session_list_limit(
    fake_project_setup, tmp_transcript_root_with_3_sessions, monkeypatch
):
    """--limit=1 returns at most 1 session."""
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_3_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "list", "--limit", "1", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["ok"] is True
    assert len(data["sessions"]) <= 1


# ---------------------------------------------------------------------------
# test_session_show_not_found
# ---------------------------------------------------------------------------

def test_session_show_not_found(fake_project_setup, tmp_transcript_root_with_2_sessions, monkeypatch):
    repo = fake_project_setup
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    monkeypatch.setenv("PKM_DATA_REPO", str(repo))

    result = runner.invoke(app, ["session", "show", "no-such-uuid", "--json"])
    assert result.exit_code != 0
    data = json.loads(result.output.strip())
    assert data["ok"] is False
    assert data["error"]["code"] == "NOT_FOUND"
