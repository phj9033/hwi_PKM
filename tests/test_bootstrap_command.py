"""Tests for `pkm bootstrap` — chains [init →] doctor download → reindex → dashboard.

The bootstrap command shells out to ``python -m pkm <subcommand>`` for each
step. Tests monkeypatch ``subprocess.run`` so we never actually fork. See
M6.12 in `docs/superpowers/plans/2026-05-02-pkm-m6-dashboard.md`.

The init step is conditional on ``_needs_init(cwd)`` (no ``data/`` and no
``.pkm/``). Tests that exercise the original 3-step flow pre-create those
markers via ``_mark_initialized()``; tests for the auto-init branch leave
``tmp_path`` empty.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _mark_initialized(root: Path) -> None:
    """Stand in for the artifacts a real ``pkm init`` (or git clone) leaves.

    Bootstrap's ``_needs_init`` skips the init step when either ``data/`` or
    ``.pkm/`` is present, mirroring init's own collision check.
    """
    (root / "data").mkdir()
    (root / ".pkm").mkdir()


def test_bootstrap_runs_three_steps_in_order(tmp_path, monkeypatch):
    """All three subprocess invocations happen, in the documented order."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        # cmd[0] = sys.executable, cmd[1] = "-m", cmd[2:] = ["pkm", ...]
        calls.append(cmd[2:])

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    _mark_initialized(tmp_path)
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    assert calls == [
        ["pkm", "doctor", "--download"],
        ["pkm", "reindex", "db", "--full"],
        ["pkm", "dashboard", "build"],
    ]


def test_bootstrap_aborts_on_doctor_failure(tmp_path, monkeypatch):
    """Doctor non-zero exit aborts before reindex/dashboard run."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd[2:])

        class R:
            returncode = 2
            stdout = ""
            stderr = "model fetch failed"

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    _mark_initialized(tmp_path)
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    # Only doctor was attempted.
    assert len(calls) == 1
    combined = (result.stdout or "") + " " + (result.stderr or "")
    assert "doctor" in combined.lower()


def test_bootstrap_aborts_on_reindex_failure(tmp_path, monkeypatch):
    """Doctor passes (rc=0), reindex fails (rc=1) → abort, dashboard not invoked."""
    responses = [
        (0, ""),  # doctor succeeds
        (1, "reindex error"),  # reindex fails
    ]
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd[2:])
        rc, err = responses.pop(0)

        class R:
            returncode = rc
            stdout = ""
            stderr = err

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    _mark_initialized(tmp_path)
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    # Doctor + reindex were attempted; dashboard was NOT.
    assert len(calls) == 2
    assert calls[0] == ["pkm", "doctor", "--download"]
    assert calls[1] == ["pkm", "reindex", "db", "--full"]
    combined = (result.stdout or "") + " " + (result.stderr or "")
    assert "reindex" in combined.lower()


def test_bootstrap_json_mode(tmp_path, monkeypatch):
    """--json prints a structured step report on stdout."""

    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    _mark_initialized(tmp_path)
    result = runner.invoke(app, ["bootstrap", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "steps" in payload
    assert len(payload["steps"]) == 3
    assert all(s["ok"] for s in payload["steps"])
    names = [s["name"] for s in payload["steps"]]
    assert names == ["doctor", "reindex", "dashboard"]
    for s in payload["steps"]:
        assert "duration_s" in s
        assert isinstance(s["duration_s"], int | float)


def test_bootstrap_json_mode_on_failure(tmp_path, monkeypatch):
    """--json on a failed run still emits a structured report; first failure has hint."""

    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    _mark_initialized(tmp_path)
    result = runner.invoke(app, ["bootstrap", "--json"])
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["steps"][0]["ok"] is False
    assert "boom" in payload["steps"][0]["hint"]


def test_bootstrap_help_lists_steps():
    """`pkm bootstrap --help` mentions all sub-steps so the user knows."""
    result = runner.invoke(app, ["bootstrap", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "init" in out
    assert "doctor" in out
    assert "reindex" in out
    assert "dashboard" in out


def test_bootstrap_prepends_init_on_empty_dir(tmp_path, monkeypatch):
    """Empty dir → init runs as step 0, then the original three steps follow."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd[2:])

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    # Intentionally do NOT call _mark_initialized — directory is empty.
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    assert calls == [
        ["pkm", "init"],
        ["pkm", "doctor", "--download"],
        ["pkm", "reindex", "db", "--full"],
        ["pkm", "dashboard", "build"],
    ]


def test_bootstrap_skips_init_when_data_present(tmp_path, monkeypatch):
    """If ``data/`` already exists (fresh-clone case), init is skipped."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd[2:])

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    # Mirror a fresh git-clone: data/ present from committed source, .pkm/
    # absent (gitignored). _needs_init only false-skips if either marker
    # exists, so a single `data/` is enough.
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    assert ["pkm", "init"] not in calls
    assert calls == [
        ["pkm", "doctor", "--download"],
        ["pkm", "reindex", "db", "--full"],
        ["pkm", "dashboard", "build"],
    ]


def test_bootstrap_aborts_when_init_step_fails(tmp_path, monkeypatch):
    """If the auto-prepended init step fails, doctor/reindex/dashboard are not attempted."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd[2:])

        class R:
            returncode = 1
            stdout = ""
            stderr = "init exploded"

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    assert calls == [["pkm", "init"]]
    combined = (result.stdout or "") + " " + (result.stderr or "")
    assert "init" in combined.lower()
