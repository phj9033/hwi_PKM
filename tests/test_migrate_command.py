"""Tests for `pkm migrate` CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect

runner = CliRunner()


def test_migrate_default_is_check(tmp_path: Path):
    """Bare `pkm migrate` is a dry-run by default — reports pending without applying."""
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["migrate", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    applied_ids = [a["id"] for a in payload.get("applied", [])]
    assert 1 in applied_ids
    assert all(a.get("dry_run") for a in payload["applied"])
    conn = connect(tmp_path)
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    assert after == 0


def test_migrate_apply_advances_schema(tmp_path: Path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    # `--apply` triggers post_mutation which prints a "not a git repo" warning
    # on the second line of stdout; the JSON is on the first line.
    payload = json.loads(res.output.splitlines()[0])
    assert payload["ok"] is True
    conn = connect(tmp_path)
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    assert after >= 1


def test_migrate_no_pending_clean_output(tmp_path: Path):
    """Already at latest → ok, no applied items."""
    conn = connect(tmp_path)  # connect leaves schema_version at latest from m001+
    # Force to the highest applicable version (skipping any with-extra migrations
    # by using m001 only — the runner already ran m001 implicitly via connect's
    # schema bootstrap, so we sync to the registered max if extras are present,
    # else to m001's id of 1).
    from pkm.store.migrations._runner import discover, _is_extra_available

    available_ids = [m.id for m in discover() if _is_extra_available(m.depends_on_extra)]
    latest = max(available_ids) if available_ids else 1
    conn.execute("UPDATE schema_version SET version = ?", (latest,))
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["migrate", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload.get("applied", []) == []


def test_migrate_failure_returns_nonzero(tmp_path: Path, monkeypatch):
    """Forcing a migration to fail: exit 1, error code MIGRATION_FAILED."""
    monkeypatch.setenv("PKM_TEST_FORCE_MIGRATION_FAIL", "1")
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MIGRATION_FAILED"
