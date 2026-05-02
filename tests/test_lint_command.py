"""Tests for `pkm lint` CLI."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _seed_clean(repo: Path) -> None:
    runner.invoke(app, ["capture", "create", "--slug", "ok",
                        "--title", "OK", "--lang", "ko",
                        "--root", str(repo)],
                  input="한국어 본문 OK\n" * 10)


def test_lint_clean_repo_exits_zero(tmp_path: Path):
    repo = _init(tmp_path)
    _seed_clean(repo)
    result = runner.invoke(app, ["lint", "--json", "--root", str(repo)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_lint_with_error_exits_one(tmp_path: Path):
    repo = _init(tmp_path)
    bad = repo / "data" / "wiki" / "concepts" / "p.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntitle: P\nslug: p\nbucket: bogus\n"
                    "created_at: 2026-05-01T10:00:00+09:00\n"
                    "updated_at: 2026-05-01T10:00:00+09:00\n"
                    "status: active\nlang: ko\ntags: []\n---\nbody\n",
                   encoding="utf-8")
    result = runner.invoke(app, ["lint", "--json", "--root", str(repo)])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(e["code"] == "INVALID_VALUE" for e in payload["errors"])


def test_lint_errors_only_suppresses_warnings(tmp_path: Path):
    repo = _init(tmp_path)
    # An ORPHAN_WIKI (warning) but no errors
    p = repo / "data" / "wiki" / "concepts" / "lonely.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: L\nslug: lonely\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n---\nbody\n",
                 encoding="utf-8")
    result = runner.invoke(app, ["lint", "--errors-only", "--json", "--root", str(repo)])
    assert result.exit_code == 0  # only warnings, errors-only ignores them
    payload = json.loads(result.stdout)
    assert "warnings" not in payload or payload["warnings"] == []


def test_lint_fix_applies_fixers(tmp_path: Path):
    repo = _init(tmp_path)
    # Capture missing created_at — fixable
    p = repo / "data" / "raw" / "captures" / "2026-05-01-z.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Z\nslug: 2026-05-01-z\n"
                  "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
                 encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed missing"], cwd=repo, check=True)

    result = runner.invoke(app, ["lint", "--fix", "--json", "--root", str(repo)])
    payload = json.loads(result.stdout)
    assert payload["fixed"] >= 1
    assert "created_at:" in p.read_text(encoding="utf-8")


def test_lint_human_output_lists_findings(tmp_path: Path):
    repo = _init(tmp_path)
    bad = repo / "data" / "wiki" / "concepts" / "p.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntitle: P\nslug: p\nbucket: concepts\n"
                    "created_at: 2026-05-01T10:00:00+09:00\n"
                    "updated_at: 2026-05-01T10:00:00+09:00\n"
                    "status: weird\nlang: ko\ntags: []\n---\nbody\n",
                   encoding="utf-8")
    result = runner.invoke(app, ["lint", "--root", str(repo)])
    assert result.exit_code == 1
    assert "INVALID_VALUE" in result.stdout
    assert "data/wiki/concepts/p.md" in result.stdout
