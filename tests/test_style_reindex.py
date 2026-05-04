"""Tests for `pkm reindex --scope style` (M8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    style = tmp_path / "data" / "style" / "oauth.md"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text(
        "---\nslug: oauth\ntitle: OAuth\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: []\n---\nbody about oauth tokens.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path


def test_reindex_scope_style_indexes_sample(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "style", "--root", str(repo), "--json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] >= 1
    assert payload["stats"]["scope"] == "style"


def test_reindex_scope_all_includes_style(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "all", "--root", str(repo), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["stats"]["documents_indexed"] >= 1


def test_reindex_unknown_scope_rejected(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "nonexistent", "--root", str(repo)])
    assert result.exit_code == 1
