"""Tests for pkm.commands.index."""
from __future__ import annotations
from pathlib import Path

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def _init(tmp):
    runner.invoke(app, ["init", "--root", str(tmp)])


def test_index_rebuild_idempotent(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["index", "rebuild", "--root", str(tmp_path)])
    first = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    runner.invoke(app, ["index", "rebuild", "--root", str(tmp_path)])
    second = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert first == second
    assert "## Captures" in first
