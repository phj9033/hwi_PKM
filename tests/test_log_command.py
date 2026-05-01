"""Tests for pkm.commands.log."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init(tmp):
    runner.invoke(app, ["init", "--root", str(tmp)])


def test_log_append_basic(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(app, ["log", "append", "hello world",
                              "--type", "manual", "--ref", "n/a",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "manual" in log
    assert "hello world" in log


def test_log_show_json(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["log", "append", "m1", "--type", "t", "--ref", "r",
                        "--root", str(tmp_path)])
    res = runner.invoke(app, ["log", "show", "--json", "--root", str(tmp_path)])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert any(e["message"] == "m1" for e in payload["events"])


def test_log_show_filter_type(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["log", "append", "a", "--type", "x", "--ref", "1",
                        "--root", str(tmp_path)])
    runner.invoke(app, ["log", "append", "b", "--type", "y", "--ref", "2",
                        "--root", str(tmp_path)])
    res = runner.invoke(app, ["log", "show", "--type", "x", "--json",
                              "--root", str(tmp_path)])
    payload = json.loads(res.output)
    assert all(e["type"] == "x" for e in payload["events"])
