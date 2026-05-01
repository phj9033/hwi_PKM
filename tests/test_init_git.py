"""Tests for git initialization at the end of `pkm init`."""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app


def test_init_creates_git_repo(tmp_path: Path):
    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / ".git").is_dir()


def test_init_creates_initial_commit(tmp_path: Path):
    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=tmp_path,
        capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip().startswith("pkm init")


def test_init_idempotent_on_existing_git(tmp_path: Path):
    """If a git repo already exists, init should leave it alone (no second
    init), but still complete the rest of the scaffold."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "u@e"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "u"], cwd=tmp_path, check=True)
    head_before = (tmp_path / ".git" / "HEAD").read_text()

    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output

    head_after = (tmp_path / ".git" / "HEAD").read_text()
    assert head_before == head_after  # branch unchanged


def test_init_initial_commit_includes_scaffold(tmp_path: Path):
    """The initial commit should include SCHEMA.md, .gitignore,
    .pkm/config.toml, .claude/settings.json — the public scaffold."""
    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output

    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "SCHEMA.md" in out
    assert ".gitignore" in out
    assert ".pkm/config.toml" in out
    assert ".claude/settings.json" in out
