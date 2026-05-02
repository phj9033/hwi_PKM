"""Tests for `pkm promote`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_capture(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app,
        ["capture", "create", "--slug", "oauth-token-storage",
         "--title", "OAuth Token Storage", "--lang", "ko",
         "--root", str(tmp_path)],
        input="Body of the OAuth capture.\n",
    )
    return tmp_path


def _set_status_reviewed(repo: Path, slug_substr: str) -> None:
    runner.invoke(app, ["capture", "set-status", slug_substr, "reviewed",
                        "--root", str(repo)])


def test_promote_happy_path(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    # Default slug = capture slug stripped of date prefix
    assert payload["wiki_path"].startswith("data/wiki/concepts/")
    assert payload["wiki_path"].endswith("oauth-token-storage.md")
    assert payload["git_commit"] is not None

    # Wiki file exists with expected frontmatter
    wiki = repo_with_capture / payload["wiki_path"]
    text = wiki.read_text(encoding="utf-8")
    assert "bucket: concepts" in text
    assert "status: stub" in text
    assert "promoted_from: data/raw/captures/" in text

    # Capture status flipped to archived
    cap_dir = repo_with_capture / "data" / "raw" / "captures"
    cap_files = list(cap_dir.glob("*oauth-token-storage*.md"))
    assert len(cap_files) == 1
    assert "status: archived" in cap_files[0].read_text(encoding="utf-8")


def test_promote_rejects_draft_status(repo_with_capture: Path):
    # Source is still draft (we didn't mark it reviewed)
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "STATUS_NOT_REVIEWED"


def test_promote_unknown_bucket(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "garbage",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_promote_keep_source(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--keep-source",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0
    cap_files = list((repo_with_capture / "data" / "raw" / "captures").glob("*oauth*.md"))
    assert "status: reviewed" in cap_files[0].read_text(encoding="utf-8")


def test_promote_with_custom_slug(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "notes",
              "--slug", "ots-summary",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["wiki_path"].endswith("notes/ots-summary.md")


def test_promote_collision_existing_wiki_path(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    # Pre-create a wiki file at the destination
    target = repo_with_capture / "data" / "wiki" / "concepts" / "oauth-token-storage.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntitle: x\nslug: oauth-token-storage\nbucket: concepts\n"
                       "created_at: 2026-05-01T10:00:00+09:00\n"
                       "updated_at: 2026-05-01T10:00:00+09:00\n"
                       "status: stub\nlang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_with_capture, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wiki"], cwd=repo_with_capture, check=True)

    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "STATE_ERROR"


def test_promote_writing_input_returns_carve_error(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Manually drop a writing file (write new is M5)
    w = tmp_path / "data" / "writing" / "x.md"
    w.write_text("---\ntitle: t\nslug: x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: final\npurpose: report\n"
                  "derived_from: [data/wiki/concepts/y.md]\n"
                  "lang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed writing"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["promote", "data/writing/x.md", "--to", "concepts",
              "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "PROMOTE_FROM_WRITING_NOT_YET"


def test_promote_chunk_input_rejected(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(app, ["chunks", "new", "oauth-deep-dive", "--root", str(tmp_path)])
    result = runner.invoke(
        app, ["promote", "data/raw/chunks/oauth-deep-dive", "--to", "concepts",
              "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_promote_emits_event(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture)],
    )
    log = (repo_with_capture / "data" / "log.md").read_text(encoding="utf-8")
    assert "capture.promote" in log
