"""Canonicalize git remote URLs to <host>:<path> for stable matching."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


_SSH_RX = re.compile(r"^(?:ssh://)?(?:[^@]+@)?(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?/?$")
_HTTPS_RX = re.compile(r"^https?://(?P<host>[^/:]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?/?$")


def normalize_remote(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    m = _HTTPS_RX.match(url)
    if m:
        return f"{m['host']}:{m['path']}"
    m = _SSH_RX.match(url)
    if m:
        return f"{m['host']}:{m['path']}"
    return None


def discover_remote(cwd: Path) -> str | None:
    """Run `git remote get-url origin` in cwd. Return normalized form or None."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return normalize_remote(out.stdout)
