"""Tests for `pkm search --scope style` (M8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_style(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    style = tmp_path / "data" / "style" / "oauth-token-storage.md"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text(
        "---\nslug: oauth-token-storage\ntitle: OAuth\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: [auth]\n---\n"
        "OAuth 토큰을 안전하게 저장하는 방법에 대해 다룬다.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    runner.invoke(app, ["reindex", "db", "--scope", "style", "--root", str(tmp_path)])
    return tmp_path


def test_search_scope_style_returns_sample(repo_with_style: Path):
    result = runner.invoke(
        app,
        ["search", "OAuth 토큰", "--scope", "style", "--no-rerank", "--root", str(repo_with_style), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    paths = [r["path"] for r in payload["results"]]
    assert any("data/style/oauth-token-storage.md" in p for p in paths)


def test_search_scope_style_excludes_other_buckets(repo_with_style: Path, tmp_path):
    # Add a wiki page with similar content
    wiki = repo_with_style / "data" / "wiki" / "concepts" / "oauth.md"
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(
        "---\nslug: oauth\ntitle: OAuth\nbucket: concepts\nstatus: stub\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: []\n---\nOAuth 토큰 wiki entry.\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["reindex", "db", "--scope", "all", "--root", str(repo_with_style)])
    result = runner.invoke(
        app,
        ["search", "OAuth 토큰", "--scope", "style", "--no-rerank", "--root", str(repo_with_style), "--json"],
    )
    payload = json.loads(result.stdout)
    paths = [r["path"] for r in payload["results"]]
    assert all(not p.startswith("data/wiki/") for p in paths)
