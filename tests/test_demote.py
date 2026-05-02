"""Tests for `pkm demote`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_promoted(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app,
        ["capture", "create", "--slug", "csrf",
         "--title", "CSRF", "--lang", "ko",
         "--root", str(tmp_path)],
        input="csrf body\n",
    )
    runner.invoke(app, ["capture", "set-status", "csrf", "reviewed", "--root", str(tmp_path)])
    runner.invoke(app, ["promote", "csrf", "--to", "concepts", "--root", str(tmp_path)])
    return tmp_path


def test_demote_round_trips_to_reviewed(repo_with_promoted: Path):
    result = runner.invoke(
        app, ["demote", "concepts/csrf", "--root", str(repo_with_promoted), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    # Wiki file gone
    assert not (repo_with_promoted / "data" / "wiki" / "concepts" / "csrf.md").exists()
    # Source capture restored to status=reviewed
    cap = next((repo_with_promoted / "data" / "raw" / "captures").glob("*csrf*.md"))
    assert "status: reviewed" in cap.read_text(encoding="utf-8")


def test_demote_missing_promoted_from(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Hand-author a wiki page without promoted_from
    p = tmp_path / "data" / "wiki" / "concepts" / "orphan.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Orphan\nslug: orphan\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed orphan"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["demote", "concepts/orphan", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] in ("STATE_ERROR", "VALIDATION_ERROR")


def test_demote_writing_origin_returns_carve_error(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / "data" / "wiki" / "concepts" / "writing-origin.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: WO\nslug: writing-origin\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n"
                  "promoted_from: data/writing/some.md\n---\nbody\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wo"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["demote", "concepts/writing-origin", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "DEMOTE_TO_WRITING_NOT_YET"


def test_demote_unknown_wiki_ref(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    result = runner.invoke(
        app, ["demote", "concepts/nope", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "NOT_FOUND"


def test_demote_emits_event(repo_with_promoted: Path):
    runner.invoke(app, ["demote", "concepts/csrf", "--root", str(repo_with_promoted)])
    log = (repo_with_promoted / "data" / "log.md").read_text(encoding="utf-8")
    assert "wiki.demote" in log
