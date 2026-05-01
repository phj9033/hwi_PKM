"""Git auto-commit primitives.

Thin wrapper over the `git` CLI via `subprocess.run`. Three functions:

- `is_git_repo(root)` — bool
- `git_init(root)` — idempotent; bootstraps `.git/` and basic config if missing
- `commit_paths(root, paths, message) -> str | None` — single commit; returns
  the 40-char SHA, or None if the repo is missing OR there was nothing to
  commit (idempotent re-runs).

The caller decides what to do with `None`. Master spec §6.6 step 4.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path, *, check: bool = True,
         capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
    )


def is_git_repo(root: Path) -> bool:
    """Return True iff `root` is inside a git working tree."""
    if not (root / ".git").exists():
        return False
    try:
        out = _run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root, check=False,
        )
    except FileNotFoundError:
        # `git` not installed
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def git_init(root: Path) -> None:
    """Bootstrap a git repo at `root`. Idempotent.

    If `.git/` already exists, do nothing. Otherwise:
      1. `git init -q -b main`
      2. If user.email / user.name aren't set globally, set repo-local
         defaults so the very first `pkm` commit doesn't fail.
    """
    if (root / ".git").exists():
        return
    _run(["git", "init", "-q", "-b", "main"], cwd=root)
    for key, fallback in (("user.email", "pkm@local"), ("user.name", "PKM")):
        existing = _run(["git", "config", "--get", key], cwd=root, check=False)
        if existing.returncode != 0:
            _run(["git", "config", key, fallback], cwd=root)


def commit_paths(root: Path, paths: list[str], message: str) -> str | None:
    """Stage `paths` (skipping missing ones) plus implicit log/index files,
    then create one commit. Returns the new SHA, or None if:
      - root is not a git repo, OR
      - nothing was staged (e.g. all paths were unchanged), OR
      - all paths were ignored by `.gitignore`.
    """
    if not is_git_repo(root):
        return None
    abs_paths = [str((root / p)) for p in paths if (root / p).exists()]
    if abs_paths:
        _run(["git", "add", "--", *abs_paths], cwd=root)
    diff = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    if not diff.stdout.strip():
        return None
    _run(["git", "commit", "-q", "-m", message], cwd=root)
    head = _run(["git", "rev-parse", "HEAD"], cwd=root)
    return head.stdout.strip()
