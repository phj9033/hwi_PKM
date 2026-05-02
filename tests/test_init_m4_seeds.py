"""Tests for the M4-seeded slash templates."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_init_seeds_promote_template(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / ".claude" / "commands" / "promote.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "/promote" in text
    assert "pkm promote" in text


def test_init_seeds_lint_template(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / ".claude" / "commands" / "lint.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "/lint" in text
    assert "pkm lint" in text
