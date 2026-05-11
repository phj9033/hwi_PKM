"""cwd-local `.pkm-link` marker file IO.

The marker is a hint for CLAUDE.md's fast-path. ProjectIndex remains the
single source of truth — see `pkm/session/registry.py`.

All public functions are best-effort: never raise out of this module. Callers
decide whether to surface a warning.
"""

from __future__ import annotations

from pathlib import Path

MARKER_FILENAME = ".pkm-link"


def read(cwd: Path) -> str | None:
    """Return the project_id encoded in `<cwd>/.pkm-link`, or None.

    Returns None if the marker is missing, a directory, contains non-UTF8
    bytes, is empty, or has only whitespace.
    """
    path = cwd / MARKER_FILENAME
    try:
        if not path.is_file():
            return None
    except OSError:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
