# PKM Link Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `.pkm-link` cwd-local marker so `~/.claude/CLAUDE.md` can skip `pkm project current` in non-linked projects, eliminating spurious "Error: Exit code 1" noise in unrelated cwd's.

**Architecture:** A new `pkm/marker.py` module owns marker file IO (read/write/delete/diagnose) with best-effort semantics. `pkm project link` writes the marker after a successful link, `pkm project rm` deletes it when cwd + content both match, and `pkm project doctor` gains 4 diagnostics (`MARKER_MISSING/MISMATCH/ORPHAN/INVALID`) plus a `--fix` flag to repair them. ProjectIndex remains the single source of truth; the marker is purely a hint.

**Tech Stack:** Python 3.11+, typer CLI, pytest with CliRunner. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-11-pkm-link-marker-design.md`

---

## Background — why these files (read first)

- `pkm/session/registry.py:85-131` — `resolve_project_id` is the 5-step resolver. **Do not touch.** Marker is a CLAUDE.md fast-path, not part of resolution.
- `pkm/commands/project.py:75-160` — `link` command success path ends at line 151. Marker write hooks in just before the closing `try` block on `payload`.
- `pkm/commands/project.py:266-330` — `rm` command. After project removal, decide whether to delete marker (cwd + content match).
- `pkm/commands/doctor.py:308-465` — `_render_human` and `doctor_cmd` orchestrate items. New diagnostics get added to the `items: list[_Item]` accumulation. `--fix` is a new flag that mutates state instead of just reporting.
- `pkm/errors.py:165-200` — existing `PKMNotLinked`, `PKMAlreadyLinked` pattern. No new error classes needed (marker errors are stderr warnings, not raised exceptions).
- `tests/conftest.py:118-146` — `tmp_data_repo`, `tmp_code_repo`, `tmp_code_repo_pair` fixtures are the standard for link/rm/doctor tests.
- `tests/test_project_link.py` — existing pattern for link tests. Use as model for marker tests.

---

## File Structure

**Created:**
- `pkm/marker.py` — read/write/delete/diagnose utilities (single responsibility)
- `tests/test_marker.py` — unit tests for `pkm.marker`
- `tests/test_project_link_marker.py` — integration: link writes marker
- `tests/test_project_rm_marker.py` — integration: rm deletes marker when matched
- `tests/test_doctor_marker.py` — integration: doctor diagnostics + --fix

**Modified:**
- `pkm/commands/project.py` — `link` and `rm` invoke marker utilities
- `pkm/commands/doctor.py` — new diagnostics + `--fix` flag
- `docs/FEATURES.md` — M14 project section gains "cwd marker" paragraph
- `README.md` — PKM linking section gains 1-line marker mention (only if section exists)

**No changes:**
- `pkm/session/registry.py` — resolver untouched (SoT preserved)
- `pkm/commands/project.py::current` — unchanged
- Other commands

---

## Conventions

- **Marker filename:** `.pkm-link` (literal). No version suffix, no env-overridable name. Constant lives in `pkm/marker.py` as `MARKER_FILENAME`.
- **Marker content:** `<project_id>\n`. UTF-8. `read()` accepts the first non-empty line, stripped.
- **Failure mode:** Marker IO never raises out of `pkm/marker.py`. Failures return `False`/`None`. Callers surface a 1-line stderr warning when failure is meaningful (link/rm).
- **Test isolation:** Every marker test uses `tmp_code_repo` for cwd and `tmp_data_repo` for the data repo. Never touch real `$HOME`.

---

## Task 1: Create `pkm/marker.py` skeleton + `read()`

**Files:**
- Create: `pkm/marker.py`
- Create: `tests/test_marker.py`

- [ ] **Step 1: Write the failing tests for `read()`**

Create `tests/test_marker.py`:

```python
"""Unit tests for pkm.marker — cwd-local .pkm-link file IO."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm import marker


def test_read_missing_returns_none(tmp_path: Path):
    assert marker.read(tmp_path) is None


def test_read_single_line(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("my-app\n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_strips_whitespace(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("  my-app  \n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_first_non_empty_line(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("\n\nmy-app\nextra-line\n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_empty_file_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("", encoding="utf-8")
    assert marker.read(tmp_path) is None


def test_read_whitespace_only_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("   \n\n  \n", encoding="utf-8")
    assert marker.read(tmp_path) is None


def test_read_directory_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").mkdir()
    assert marker.read(tmp_path) is None


def test_read_non_utf8_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_bytes(b"\xff\xfe not utf8")
    assert marker.read(tmp_path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_marker.py -v`
Expected: ALL FAIL with `ModuleNotFoundError: No module named 'pkm.marker'`.

- [ ] **Step 3: Create `pkm/marker.py` with `read()` only**

Create `pkm/marker.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_marker.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pkm/marker.py tests/test_marker.py
git commit -m "feat(marker): add pkm.marker.read() for .pkm-link parsing"
```

---

## Task 2: Add `write()` and `delete()` to `pkm/marker.py`

**Files:**
- Modify: `pkm/marker.py`
- Modify: `tests/test_marker.py`

- [ ] **Step 1: Append failing tests for `write()` and `delete()`**

Append to `tests/test_marker.py`:

```python
def test_write_new_file(tmp_path: Path):
    assert marker.write(tmp_path, "my-app") is True
    assert (tmp_path / ".pkm-link").read_text(encoding="utf-8") == "my-app\n"


def test_write_overwrites_existing(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("old-id\n", encoding="utf-8")
    assert marker.write(tmp_path, "new-id") is True
    assert (tmp_path / ".pkm-link").read_text(encoding="utf-8") == "new-id\n"


def test_write_readonly_dir_returns_false(tmp_path: Path):
    import os
    sub = tmp_path / "ro"
    sub.mkdir()
    os.chmod(sub, 0o500)  # r-x — no write
    try:
        assert marker.write(sub, "x") is False
    finally:
        os.chmod(sub, 0o700)  # restore so tmp_path cleanup works


def test_delete_existing(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("x\n", encoding="utf-8")
    assert marker.delete(tmp_path) is True
    assert not (tmp_path / ".pkm-link").exists()


def test_delete_missing_returns_true(tmp_path: Path):
    # Idempotent: nothing to delete is success.
    assert marker.delete(tmp_path) is True


def test_delete_directory_returns_false(tmp_path: Path):
    (tmp_path / ".pkm-link").mkdir()
    assert marker.delete(tmp_path) is False
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_marker.py -v`
Expected: 6 new tests fail with `AttributeError: module 'pkm.marker' has no attribute 'write'/'delete'`.

- [ ] **Step 3: Add `write()` and `delete()` to `pkm/marker.py`**

Append to `pkm/marker.py`:

```python
def write(cwd: Path, project_id: str) -> bool:
    """Write `<cwd>/.pkm-link` with `<project_id>\\n`. Overwrites if present.

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_marker.py -v`
Expected: 14 passed (8 from Task 1 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add pkm/marker.py tests/test_marker.py
git commit -m "feat(marker): add write() and delete() with best-effort semantics"
```

---

## Task 3: Add `diagnose()` to `pkm/marker.py`

**Files:**
- Modify: `pkm/marker.py`
- Modify: `tests/test_marker.py`

- [ ] **Step 1: Append failing tests for `diagnose()`**

Append to `tests/test_marker.py`:

```python
def test_diagnose_clean_when_linked_with_matching_marker(tmp_path: Path):
    marker.write(tmp_path, "my-app")
    assert marker.diagnose(tmp_path, resolved_id="my-app") is None


def test_diagnose_clean_when_not_linked_and_no_marker(tmp_path: Path):
    assert marker.diagnose(tmp_path, resolved_id=None) is None


def test_diagnose_marker_missing(tmp_path: Path):
    d = marker.diagnose(tmp_path, resolved_id="my-app")
    assert d is not None
    assert d.code == "MARKER_MISSING"
    assert "my-app" in d.detail


def test_diagnose_marker_mismatch(tmp_path: Path):
    marker.write(tmp_path, "old-id")
    d = marker.diagnose(tmp_path, resolved_id="new-id")
    assert d is not None
    assert d.code == "MARKER_MISMATCH"
    assert "old-id" in d.detail and "new-id" in d.detail


def test_diagnose_marker_orphan(tmp_path: Path):
    marker.write(tmp_path, "stale-id")
    d = marker.diagnose(tmp_path, resolved_id=None)
    assert d is not None
    assert d.code == "MARKER_ORPHAN"
    assert "stale-id" in d.detail


def test_diagnose_marker_invalid_directory(tmp_path: Path):
    (tmp_path / ".pkm-link").mkdir()
    d = marker.diagnose(tmp_path, resolved_id="my-app")
    assert d is not None
    assert d.code == "MARKER_INVALID"


def test_diagnose_marker_invalid_empty(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("\n  \n", encoding="utf-8")
    d = marker.diagnose(tmp_path, resolved_id="my-app")
    assert d is not None
    assert d.code == "MARKER_INVALID"
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_marker.py -v`
Expected: 7 new tests fail with `AttributeError: ... 'diagnose'`.

- [ ] **Step 3: Add `MarkerDiagnosis` dataclass + `diagnose()`**

Append to `pkm/marker.py`:

```python
from dataclasses import dataclass


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_marker.py -v`
Expected: 21 passed (14 + 7 new).

- [ ] **Step 5: Commit**

```bash
git add pkm/marker.py tests/test_marker.py
git commit -m "feat(marker): add diagnose() returning MARKER_MISSING/MISMATCH/ORPHAN/INVALID"
```

---

## Task 4: `pkm project link` writes marker

**Files:**
- Modify: `pkm/commands/project.py` — `link` command success path
- Create: `tests/test_project_link_marker.py`

- [ ] **Step 1: Write the failing test for marker creation on link**

Create `tests/test_project_link_marker.py`:

```python
"""`pkm project link` writes a `.pkm-link` marker to cwd (best-effort)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_link_writes_marker_to_cwd(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    marker_path = tmp_code_repo / ".pkm-link"
    assert marker_path.is_file()
    assert marker_path.read_text(encoding="utf-8") == "my-app\n"


def test_link_json_payload_includes_marker_written(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["marker_written"] is True


def test_link_idempotent_re_writes_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    # Manually delete marker, then re-link
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    # ALREADY_LINKED is exit_code 0 per PKMAlreadyLinked.exit_code=0; marker should be recreated
    assert (tmp_code_repo / ".pkm-link").is_file()


def test_link_readonly_cwd_succeeds_with_warning(tmp_data_repo, tmp_code_repo, monkeypatch, capsys):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    os.chmod(tmp_code_repo, 0o500)
    try:
        result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    finally:
        os.chmod(tmp_code_repo, 0o700)
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["marker_written"] is False
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_project_link_marker.py -v`
Expected: All 4 fail — marker not written, `marker_written` key missing.

- [ ] **Step 3: Add marker write to `link` command**

Edit `pkm/commands/project.py`. Add import near the top:

```python
from pkm import marker
```

In the `link` function, replace the success-path block (currently lines ~147-151):

```python
            payload = {"ok": True, "project_id": pid, "data_dir": f"data/projects/{pid}"}
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"linked: {pid} -> data/projects/{pid}")
```

With:

```python
            marker_written = marker.write(cwd, pid)
            if not marker_written:
                typer.echo(
                    f"warning: failed to write {marker.MARKER_FILENAME} marker in {cwd}",
                    err=True,
                )

            payload = {
                "ok": True,
                "project_id": pid,
                "data_dir": f"data/projects/{pid}",
                "marker_written": marker_written,
            }
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"linked: {pid} -> data/projects/{pid}")
```

**Also handle `ALREADY_LINKED` idempotent re-link:** The current `link` raises `PKMAlreadyLinked` before reaching the success path, so the existing exception branch needs to also attempt marker write. Locate the `except (PKMNotAGitRepo, PKMAlreadyLinked, ...)` block (around line 153). Modify to:

```python
        except PKMAlreadyLinked as e:
            # Idempotent: marker may be missing — recreate it best-effort.
            # We can recover the project_id from `pid` if it was computed,
            # else from the existing record.
            try:
                marker.write(cwd, pid)
            except Exception:  # pragma: no cover — write() is best-effort
                pass
            _emit_error_envelope(e, json_out)
        except (PKMNotAGitRepo, PKMProjectIdConflict, PKMInvalidProjectId, PKMValidationError) as e:
            _emit_error_envelope(e, json_out)
```

Note: `pid` may not be defined if `PKMNotAGitRepo` fired before id resolution; that's fine because `PKMAlreadyLinked` only fires *after* id is computed (see line 113-114). For safety, guard the marker write with `if 'pid' in locals():`. Final form:

```python
        except PKMAlreadyLinked as e:
            if "pid" in locals():
                marker.write(cwd, pid)  # best-effort
            _emit_error_envelope(e, json_out)
        except (PKMNotAGitRepo, PKMProjectIdConflict, PKMInvalidProjectId, PKMValidationError) as e:
            _emit_error_envelope(e, json_out)
```

Also extract the error envelope logic into a helper. The existing module already has `_emit_error_envelope` at line 49; reuse it. (The current code inlines the JSON dump in the except block — that's the cleanup target. If splitting the except blocks proves too invasive, simply call `_emit_error_envelope(e, json_out)` and accept the existing two-branch structure.)

- [ ] **Step 4: Run new tests + existing link tests to verify no regression**

Run: `uv run pytest tests/test_project_link_marker.py tests/test_project_link.py -v`
Expected: 4 new + all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add pkm/commands/project.py tests/test_project_link_marker.py
git commit -m "feat(project): pkm project link writes .pkm-link marker (best-effort)"
```

---

## Task 5: `pkm project rm` deletes marker on cwd + content match

**Files:**
- Modify: `pkm/commands/project.py` — `rm` command success path
- Create: `tests/test_project_rm_marker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_rm_marker.py`:

```python
"""`pkm project rm` deletes .pkm-link only when cwd matches AND marker content matches."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_rm_deletes_marker_when_cwd_matches(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").is_file()
    result = runner.invoke(app, ["project", "rm", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_rm_preserves_marker_when_content_mismatches(tmp_data_repo, tmp_code_repo, monkeypatch):
    """If marker exists but contains a different project_id, leave it alone."""
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    # Tamper marker to point at a different id
    (tmp_code_repo / ".pkm-link").write_text("other-id\n", encoding="utf-8")
    runner.invoke(app, ["project", "rm", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").is_file()
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "other-id"


def test_rm_preserves_marker_when_cwd_not_matched(tmp_data_repo, tmp_code_repo_pair, monkeypatch):
    """rm from a different cwd than where link happened → marker untouched."""
    repo_a, repo_b = tmp_code_repo_pair
    _git_init(repo_a, remote="git@github.com:a/a.git")
    _git_init(repo_b, remote="git@github.com:b/b.git")
    monkeypatch.chdir(repo_a)
    runner.invoke(app, ["project", "link", "--id", "proj-a", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (repo_a / ".pkm-link").is_file()
    # rm from repo_b's cwd
    monkeypatch.chdir(repo_b)
    runner.invoke(app, ["project", "rm", "proj-a", "--no-commit", "--data-repo", str(tmp_data_repo)])
    # repo_a's marker is stale orphan — left for `doctor` to clean up later
    assert (repo_a / ".pkm-link").is_file()
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_project_rm_marker.py -v`
Expected: All 3 fail because `rm` does not touch the marker today.

- [ ] **Step 3: Add marker delete logic to `rm` command**

Edit `pkm/commands/project.py`. In the `rm` function, after the project directory cleanup and before the auto-commit block (around line 305), insert:

```python
            # Best-effort marker cleanup: only when cwd matches this project's
            # registered remote/local_paths AND the marker content matches the
            # removed id. Content mismatch = different project's marker → leave.
            cwd = Path.cwd()
            cwd_matches = False
            try:
                from pkm.session.git_remote import discover_remote, normalize_remote
                raw = discover_remote(cwd)
                canon = normalize_remote(raw) if raw else None
                if canon and canon in record.git_remotes:
                    cwd_matches = True
                else:
                    cwd_str = str(cwd.resolve())
                    for lp in record.local_paths:
                        try:
                            rp = str(Path(lp).expanduser().resolve())
                        except OSError:
                            rp = lp
                        if cwd_str == rp or cwd_str.startswith(rp + "/"):
                            cwd_matches = True
                            break
            except Exception:
                cwd_matches = False

            if cwd_matches:
                marker_id = marker.read(cwd)
                if marker_id == project_id:
                    if not marker.delete(cwd):
                        typer.echo(
                            f"warning: failed to delete {marker.MARKER_FILENAME} in {cwd}",
                            err=True,
                        )
                elif marker_id is not None and marker_id != project_id:
                    typer.echo(
                        f"warning: {marker.MARKER_FILENAME} contains {marker_id!r}, not {project_id!r} — left in place",
                        err=True,
                    )
```

Note: `record` (the ProjectRecord) is already in scope from line 280 in the existing `rm` body.

- [ ] **Step 4: Run new tests + existing rm tests to verify**

Run: `uv run pytest tests/test_project_rm_marker.py tests/test_project_link.py -v`
Expected: All pass.

If a project_rm regression test file exists (`tests/test_project_*.py`), run it too. Use:

```bash
uv run pytest tests/ -k "project_rm or project_link" -v
```

- [ ] **Step 5: Commit**

```bash
git add pkm/commands/project.py tests/test_project_rm_marker.py
git commit -m "feat(project): pkm project rm deletes marker on cwd+content match"
```

---

## Task 6: `pkm project doctor` adds 4 diagnostics

**Files:**
- Modify: `pkm/commands/doctor.py` — add `_check_marker` function + integrate into items list
- Create: `tests/test_doctor_marker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_doctor_marker.py`:

```python
"""`pkm doctor` surfaces marker diagnostics for the cwd."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def _doctor_marker_item(json_output: str) -> dict | None:
    payload = json.loads(json_output)
    for item in payload["items"]:
        if item["name"] == "marker":
            return item
    return None


def test_doctor_marker_ok_when_linked_and_marker_matches(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "ok"


def test_doctor_marker_missing(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "missing"
    assert "MARKER_MISSING" in (item["detail"] or "")


def test_doctor_marker_mismatch(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").write_text("wrong-id\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_MISMATCH" in (item["detail"] or "")


def test_doctor_marker_orphan(tmp_data_repo, tmp_code_repo, monkeypatch):
    # No link; just a stray marker
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").write_text("stale\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_ORPHAN" in (item["detail"] or "")


def test_doctor_marker_invalid(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").mkdir()
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_INVALID" in (item["detail"] or "")


def test_doctor_marker_ok_when_not_linked_and_no_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_doctor_marker.py -v`
Expected: All 6 fail — no `marker` item in doctor output.

- [ ] **Step 3: Add `_check_marker` to `pkm/commands/doctor.py`**

Edit `pkm/commands/doctor.py`. Add this function near the other `_check_*` functions (after `_check_current_project` around line 175):

```python
def _check_marker(repo: Path) -> _Item:
    """cwd-local .pkm-link consistency check.

    Returns status=ok when marker state matches resolver, else status=missing
    with detail prefixed by the diagnosis code (MARKER_MISSING/MISMATCH/
    ORPHAN/INVALID).
    """
    from pkm import marker
    from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id

    try:
        idx = ProjectIndex.load(repo)
        ovs = load_local_overrides(repo)
        pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
    except Exception as e:  # noqa: BLE001
        return _Item("marker", "error", f"resolve failed: {type(e).__name__}")

    diag = marker.diagnose(Path.cwd(), pid)
    if diag is None:
        return _Item("marker", "ok", None)
    return _Item("marker", "missing", f"{diag.code}: {diag.detail}")
```

Then in `doctor_cmd` (around line 391, after `_check_current_project`), add:

```python
        items.append(_check_marker(root))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_doctor_marker.py tests/test_doctor.py -v`
Expected: 6 new + all existing pass.

- [ ] **Step 5: Commit**

```bash
git add pkm/commands/doctor.py tests/test_doctor_marker.py
git commit -m "feat(doctor): add marker diagnostic row (MISSING/MISMATCH/ORPHAN/INVALID)"
```

---

## Task 7: `pkm doctor --fix` repairs marker

**Files:**
- Modify: `pkm/commands/doctor.py` — add `--fix` flag, wire to marker repair
- Modify: `tests/test_doctor_marker.py` — add `--fix` tests

- [ ] **Step 1: Append failing tests**

Append to `tests/test_doctor_marker.py`:

```python
def test_doctor_fix_creates_missing_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["doctor", "--fix", "--json", "--root", str(tmp_data_repo)])
    assert result.exit_code == 0
    assert (tmp_code_repo / ".pkm-link").is_file()
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "my-app"


def test_doctor_fix_overwrites_mismatched_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").write_text("wrong\n", encoding="utf-8")
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "my-app"


def test_doctor_fix_removes_orphan_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").write_text("stale\n", encoding="utf-8")
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_doctor_fix_removes_invalid_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").mkdir()
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    # Invalid removed; nothing recreated since cwd is NOT_LINKED
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_doctor_without_fix_does_not_mutate(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    runner.invoke(app, ["doctor", "--root", str(tmp_data_repo)])
    # No --fix → marker remains absent
    assert not (tmp_code_repo / ".pkm-link").exists()
```

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_doctor_marker.py -v -k fix`
Expected: 4 fail with `Usage Error: No such option: --fix`. The non-fix test passes (it just doesn't depend on `--fix`).

- [ ] **Step 3: Add `--fix` to `doctor_cmd`**

Edit `pkm/commands/doctor.py`. In `doctor_cmd` signature, add a new typer.Option (alongside `--strict`, `--json`, `--download`):

```python
        fix: bool = typer.Option(
            False,
            "--fix",
            help="Repair marker drift (creates/overwrites/removes .pkm-link as needed).",
        ),
```

After `_check_marker` runs and is appended to items (in `doctor_cmd`), add this block (still inside `doctor_cmd`, before the JSON/human rendering):

```python
        if fix:
            from pkm import marker
            from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id

            cwd = Path.cwd()
            try:
                idx = ProjectIndex.load(root)
                ovs = load_local_overrides(root)
                resolved_pid = resolve_project_id(cwd, project_index=idx, local_overrides=ovs)
            except Exception:  # noqa: BLE001
                resolved_pid = None

            diag = marker.diagnose(cwd, resolved_pid)
            if diag is not None:
                if diag.code in ("MARKER_MISSING", "MARKER_MISMATCH"):
                    marker.write(cwd, resolved_pid)  # type: ignore[arg-type]
                elif diag.code in ("MARKER_ORPHAN", "MARKER_INVALID"):
                    marker.delete(cwd)
                # Refresh the marker row after fix
                for i, it in enumerate(items):
                    if it.name == "marker":
                        items[i] = _check_marker(root)
                        break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_doctor_marker.py tests/test_doctor.py -v`
Expected: 10 marker tests + all existing doctor tests pass.

- [ ] **Step 5: Commit**

```bash
git add pkm/commands/doctor.py tests/test_doctor_marker.py
git commit -m "feat(doctor): add --fix to repair marker drift"
```

---

## Task 8: Update FEATURES.md + README

**Files:**
- Modify: `docs/FEATURES.md`
- Modify: `README.md` (only if it references PKM project linking)

- [ ] **Step 1: Add marker paragraph to FEATURES.md M14 section**

Locate the M14 / Projects section in `docs/FEATURES.md` (around line 215, the `## 프로젝트 (M14)` block or similar — search for `pkm project link`). After the existing CLI table, add:

```markdown
**cwd 마커 (`.pkm-link`):** `pkm project link` 는 cwd 에 `.pkm-link` 파일을 생성한다 (내용: `<project_id>\n`). 이 마커는 `~/.claude/CLAUDE.md` 의 PKM 컨텍스트 로딩 fast-path 가 미링크 디렉토리에서 `pkm project current` 호출을 회피하기 위한 hint 다. ProjectIndex 가 여전히 SoT 이므로 마커 동기화 실수가 데이터 무결성에 영향을 주지 않는다. `pkm project doctor --fix` 가 누락/불일치/orphan/invalid 4종을 자동 복구. 팀이 같은 PKM data repo 를 공유하지 않는다면 `.pkm-link` 를 `.gitignore` 에 추가하는 것을 권장 (per-machine link state).

권장 CLAUDE.md 블록 (글로벌, 사용자가 직접 교체):

```markdown
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Quick check: is `.pkm-link` present in cwd? If not, silently proceed.
2. If marker exists, run `pkm project current --json 2>/dev/null`.
3. If `ok: true`: invoke the `pkm:recalling-project-context` skill.
4. If marker exists but `ok: false`: silently proceed.
```
```

- [ ] **Step 2: Update README.md if PKM project linking is mentioned**

Run: `grep -n "pkm project link\|project link" README.md`

If the grep finds a section, add a single line near it:

```markdown
- `pkm project link` 은 cwd 에 `.pkm-link` 마커를 생성합니다 (CLAUDE.md fast-path 용 hint; gitignore 권장).
```

If grep finds nothing, skip this step.

- [ ] **Step 3: Verify renders**

Open `docs/FEATURES.md` and confirm the new paragraph is in the M14 section and reads cleanly.

- [ ] **Step 4: Commit**

```bash
git add docs/FEATURES.md README.md
git commit -m "docs: document .pkm-link marker and recommended CLAUDE.md block"
```

---

## Task 9: Full regression sweep

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All tests green. If any pre-existing test breaks because it now sees a marker side-effect (e.g., a test that asserts `tmp_code_repo` contents), add a targeted fix in the same task.

- [ ] **Step 2: Manual smoke test (optional but valuable)**

In this repo (already linked as `hwi_PKM`):

```bash
# Marker should be missing right now
ls -la .pkm-link 2>/dev/null && echo "EXISTS" || echo "ABSENT (expected)"

# Run doctor --fix to create it
uv run pkm doctor --fix --root . > /tmp/doctor.out
cat /tmp/doctor.out | grep -A1 "marker"

# Marker should now exist
cat .pkm-link
# Expected: hwi_PKM

# Verify gitignore status (committed or ignored)
git status .pkm-link
```

If you commit the marker by accident, remove it: `git rm --cached .pkm-link && echo .pkm-link >> .gitignore`.

- [ ] **Step 3: Commit the smoke artifact if desired**

If you generated `.pkm-link` and want to include the gitignore entry:

```bash
git add .gitignore
git commit -m "chore: gitignore .pkm-link (per-machine marker)"
```

(Skip if `.gitignore` already excludes it or you don't want the marker in this repo.)

---

## Done criteria

- [ ] All 9 tasks committed
- [ ] `uv run pytest tests/` is green
- [ ] `pkm project link` writes `.pkm-link` with project_id
- [ ] `pkm project rm` deletes `.pkm-link` only when cwd matches and content matches
- [ ] `pkm doctor` reports `marker` row with one of the 4 diagnosis codes when drift exists
- [ ] `pkm doctor --fix` repairs drift
- [ ] `docs/FEATURES.md` documents the marker and the recommended CLAUDE.md block

User-facing follow-up (out of this plan's scope): user updates their own `~/.claude/CLAUDE.md` PKM block with the new fast-path snippet.
