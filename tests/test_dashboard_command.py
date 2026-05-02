"""Smoke tests for `pkm dashboard build`. Full-build assertions land in M6.11."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_dashboard_build_creates_out_dir(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["dashboard", "build", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert (out / "index.html").exists()


def test_dashboard_build_default_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["dashboard", "build"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "dashboard" / "index.html").exists()


def test_dashboard_build_help_includes_out() -> None:
    result = runner.invoke(app, ["dashboard", "build", "--help"])
    assert result.exit_code == 0
    assert "--out" in result.stdout
