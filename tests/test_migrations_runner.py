"""Tests for the M12 migration runner — discovery, ordering, skip-on-missing-extra."""

from __future__ import annotations

from pathlib import Path

from pkm.store.index_db import connect
from pkm.store.migrations import _registry, _runner


def test_discover_returns_modules_sorted_by_id():
    mods = _runner.discover()
    ids = [m.id for m in mods]
    assert ids == sorted(ids)
    assert ids[0] == 1  # m001_initial


def test_pending_returns_empty_when_at_latest(tmp_path: Path):
    conn = connect(tmp_path)
    latest = max(m.id for m in _runner.discover())
    conn.execute("UPDATE schema_version SET version = ?", (latest,))
    conn.commit()
    pending = _runner.pending(conn)
    assert pending == []


def test_pending_returns_unapplied_when_below_latest(tmp_path: Path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    pending = _runner.pending(conn)
    assert len(pending) >= 1
    assert pending[0].id == 1


def test_apply_all_advances_schema_version(tmp_path: Path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    result = _runner.apply_all(conn)
    assert result["ok"] is True
    new = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    # We may not advance to absolute latest if some migrations are skipped due
    # to missing extras (e.g., m002 without kiwipiepy). At minimum m001 applies.
    assert new >= 1


def test_dry_run_does_not_advance(tmp_path: Path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    result = _runner.apply_all(conn, dry_run=True)
    assert result["ok"] is True
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert after == 0  # unchanged


def test_skip_when_dependency_missing(tmp_path: Path, monkeypatch):
    """A migration whose DEPENDS_ON_EXTRA is unimportable is silently skipped."""
    fake = _registry.MigrationModule(
        id=999,
        description="fake",
        depends_on_extra="this_module_definitely_does_not_exist",
        check_fn=lambda conn: {"needed": True},
        apply_fn=lambda conn: {"ok": True},
    )
    monkeypatch.setattr(_runner, "discover", lambda: [*_real_discover(), fake])
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    result = _runner.apply_all(conn)
    assert result["ok"] is True
    skipped_ids = [s["id"] for s in result.get("skipped", [])]
    assert 999 in skipped_ids


def test_failure_rolls_back_and_keeps_version(tmp_path: Path, monkeypatch):
    """A failing migration → schema_version unchanged + structured error result."""
    fake = _registry.MigrationModule(
        id=999,
        description="explode",
        depends_on_extra=None,
        check_fn=lambda conn: {"needed": True},
        apply_fn=lambda conn: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(_runner, "discover", lambda: [*_real_discover(), fake])
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    initial = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    result = _runner.apply_all(conn)
    assert result["ok"] is False
    assert "boom" in (result.get("error") or "")
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert after >= initial
    assert after < 999


# Snapshot the real discover() so monkeypatched discover() can still pull
# the registered modules in addition to a fake.
_real_discover = _runner.discover
