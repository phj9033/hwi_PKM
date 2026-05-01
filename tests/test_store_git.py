"""Tests for pkm.store.git."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pkm.store import git as gitmod

# --- is_git_repo ----

def test_is_git_repo_false_on_empty(tmp_path: Path):
    assert gitmod.is_git_repo(tmp_path) is False


def test_is_git_repo_true_after_init(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert gitmod.is_git_repo(tmp_path) is True


# --- git_init ----

def test_git_init_creates_git_dir(tmp_path: Path):
    gitmod.git_init(tmp_path)
    assert (tmp_path / ".git").is_dir()


def test_git_init_idempotent(tmp_path: Path):
    gitmod.git_init(tmp_path)
    head_before = (tmp_path / ".git" / "HEAD").read_text()
    gitmod.git_init(tmp_path)
    head_after = (tmp_path / ".git" / "HEAD").read_text()
    assert head_before == head_after


# --- commit_paths ----

def test_commit_paths_returns_sha(tmp_path: Path):
    gitmod.git_init(tmp_path)
    # Configure user so commit doesn't fail in CI envs
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("hello")
    sha = gitmod.commit_paths(tmp_path, ["a.txt"], "test: add a.txt")
    assert sha is not None
    assert len(sha) == 40
    # Verify it's a real commit
    out = subprocess.run(["git", "log", "-1", "--format=%H"], cwd=tmp_path,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == sha


def test_commit_paths_returns_none_when_no_repo(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    sha = gitmod.commit_paths(tmp_path, ["a.txt"], "test: add a.txt")
    assert sha is None


def test_commit_paths_empty_change_returns_none(tmp_path: Path):
    """Re-committing the same content yields nothing-to-commit, returns None."""
    gitmod.git_init(tmp_path)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("hello")
    gitmod.commit_paths(tmp_path, ["a.txt"], "test: initial")
    # No content changed
    sha2 = gitmod.commit_paths(tmp_path, ["a.txt"], "test: noop")
    assert sha2 is None


def test_commit_paths_handles_deleted_file(tmp_path: Path):
    """A path that was tracked then deleted on disk should still be staged
    as a deletion."""
    gitmod.git_init(tmp_path)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=tmp_path, check=True)
    f = tmp_path / "real.txt"
    f.write_text("data")
    gitmod.commit_paths(tmp_path, ["real.txt"], "test: add")
    f.unlink()
    sha = gitmod.commit_paths(tmp_path, ["real.txt"], "test: rm")
    assert sha is not None
    out = subprocess.run(
        ["git", "log", "-1", "--name-status"], cwd=tmp_path,
        capture_output=True, text=True, check=True,
    ).stdout
    assert "D\treal.txt" in out  # 'D' = deleted
