"""cwd-local `.pkm-link` marker file IO.

The marker is a hint for CLAUDE.md's fast-path. ProjectIndex remains the
single source of truth — see `pkm/session/registry.py`.

All public functions are best-effort: never raise out of this module. Callers
decide whether to surface a warning.
"""

from __future__ import annotations

from dataclasses import dataclass
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


def write(cwd: Path, project_id: str) -> bool:
    """Write `<cwd>/.pkm-link` with `<project_id>\n`. Overwrites if present.

    Returns False on any IO failure (readonly fs, permission, missing dir).
    """
    path = cwd / MARKER_FILENAME
    try:
        path.write_text(f"{project_id}\n", encoding="utf-8")
        return True
    except OSError:
        return False


def delete(cwd: Path) -> bool:
    """Remove `<cwd>/.pkm-link`. Idempotent — absence counts as success.

    Returns False if the marker exists but cannot be removed (e.g. it is a
    directory or permission is denied).
    """
    path = cwd / MARKER_FILENAME
    try:
        if not path.exists():
            return True
        if path.is_dir():
            return False
        path.unlink()
        return True
    except OSError:
        return False


@dataclass(frozen=True)
class MarkerDiagnosis:
    code: str  # MARKER_MISSING | MARKER_MISMATCH | MARKER_ORPHAN | MARKER_INVALID
    detail: str


def diagnose(cwd: Path, resolved_id: str | None) -> MarkerDiagnosis | None:
    """Compare marker state against resolver result.

    `resolved_id` is what `resolve_project_id(cwd, ...)` returned. None means
    NOT_LINKED.

    Returns None if state is clean, else a MarkerDiagnosis.
    """
    path = cwd / MARKER_FILENAME
    exists = False
    is_invalid = False
    try:
        if path.exists():
            exists = True
            if path.is_dir():
                is_invalid = True
    except OSError:
        is_invalid = True

    marker_id = read(cwd) if exists and not is_invalid else None
    # An existing file that read() couldn't parse → INVALID
    if exists and not is_invalid and marker_id is None:
        is_invalid = True

    if is_invalid:
        return MarkerDiagnosis(
            code="MARKER_INVALID",
            detail=f"{MARKER_FILENAME} exists but is unreadable (directory, non-UTF8, or empty)",
        )

    if resolved_id is None:
        if exists:
            return MarkerDiagnosis(
                code="MARKER_ORPHAN",
                detail=f"cwd is NOT_LINKED but {MARKER_FILENAME} contains {marker_id!r}",
            )
        return None

    # resolved_id is not None
    if not exists:
        return MarkerDiagnosis(
            code="MARKER_MISSING",
            detail=f"cwd is linked to {resolved_id!r} but {MARKER_FILENAME} is missing",
        )
    if marker_id != resolved_id:
        return MarkerDiagnosis(
            code="MARKER_MISMATCH",
            detail=f"{MARKER_FILENAME} contains {marker_id!r} but resolver says {resolved_id!r}",
        )
    return None
