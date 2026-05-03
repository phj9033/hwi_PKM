"""Tests for `pkm bootstrap` — chains doctor download → reindex → dashboard.

The bootstrap command shells out to ``python -m pkm <subcommand>`` for each
step. Tests monkeypatch ``subprocess.run`` so we never actually fork. See
M6.12 in `docs/superpowers/plans/2026-05-02-pkm-m6-dashboard.md`.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


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
    result = runner.invoke(app, ["bootstrap", "--json"])
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["steps"][0]["ok"] is False
    assert "boom" in payload["steps"][0]["hint"]


def test_bootstrap_help_lists_steps():
    """`pkm bootstrap --help` mentions all three sub-steps so the user knows."""
    result = runner.invoke(app, ["bootstrap", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "doctor" in out
    assert "reindex" in out
    assert "dashboard" in out
