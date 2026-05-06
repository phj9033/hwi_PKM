"""Migration runner — discovers `m<NNN>_*` modules under this package, orders
them by ID, applies any whose ID exceeds `schema_version`. Each migration runs
in its own savepoint; failure rolls back to the last good version.

Spec reference: 2026-05-06-pkm-v2-design §5.1.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
import re
import sqlite3
from typing import Any

from pkm.store.migrations import _registry

_logger = logging.getLogger(__name__)


_MIGRATION_NAME_RE = re.compile(r"^m\d{3}_")


def discover() -> list[_registry.MigrationModule]:
    """Walk this package, return every `m<NNN>_*` module wrapped as MigrationModule.

    Strict naming filter (`m\\d{3}_`) avoids picking up future siblings like
    `_metrics.py` or `migration_helpers.py`.
    """
    out: list[_registry.MigrationModule] = []
    pkg = importlib.import_module(__package__)
    for info in pkgutil.iter_modules(pkg.__path__):
        if not _MIGRATION_NAME_RE.match(info.name):
            continue
        mod = importlib.import_module(f"{__package__}.{info.name}")
        if not hasattr(mod, "ID"):
            continue
        out.append(
            _registry.MigrationModule(
                id=int(mod.ID),
                description=getattr(mod, "DESCRIPTION", ""),
                depends_on_extra=getattr(mod, "DEPENDS_ON_EXTRA", None),
                check_fn=getattr(mod, "check", lambda conn: {"needed": True}),
                apply_fn=getattr(mod, "apply"),
            )
        )
    out.sort(key=lambda m: m.id)
    return out


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    return int(row[0]) if row else 0


def pending(conn: sqlite3.Connection) -> list[_registry.MigrationModule]:
    """Migrations whose ID exceeds the current schema_version."""
    cur = _current_version(conn)
    return [m for m in discover() if m.id > cur]


def _is_extra_available(name: str | None) -> bool:
    if not name:
        return True
    # Convention: extra name maps to a top-level importable module.
    # `korean` → `kiwipiepy`. Future extras add a row.
    extra_to_module = {"korean": "kiwipiepy"}
    mod_name = extra_to_module.get(name, name)
    try:
        importlib.import_module(mod_name)
        return True
    except ImportError:
        return False


def apply_all(conn: sqlite3.Connection, *, dry_run: bool = False) -> dict[str, Any]:
    """Apply every pending migration in order. Return a structured result."""
    applied: list[dict] = []
    skipped: list[dict] = []
    error: str | None = None

    for mig in pending(conn):
        if not _is_extra_available(mig.depends_on_extra):
            skipped.append(
                {
                    "id": mig.id,
                    "description": mig.description,
                    "reason": f"missing extra '{mig.depends_on_extra}'",
                }
            )
            continue

        if dry_run:
            applied.append({"id": mig.id, "description": mig.description, "dry_run": True})
            continue

        # Test-only force-fail switch (used by the failure-mode matrix).
        if os.environ.get("PKM_TEST_FORCE_MIGRATION_FAIL") == "1":
            error = "forced failure (PKM_TEST_FORCE_MIGRATION_FAIL=1)"
            break

        try:
            conn.execute("SAVEPOINT migrate_step")
            stats = mig.apply_fn(conn)
            conn.execute("UPDATE schema_version SET version = ?", (mig.id,))
            conn.execute("RELEASE migrate_step")
            applied.append(
                {"id": mig.id, "description": mig.description, "stats": stats or {}}
            )
        except Exception as e:  # noqa: BLE001
            try:
                conn.execute("ROLLBACK TO SAVEPOINT migrate_step")
                conn.execute("RELEASE migrate_step")
            except sqlite3.OperationalError:
                # Savepoint may already be released by the failing op (FTS5 DDL).
                pass
            error = f"migration {mig.id} failed: {e}"
            _logger.exception("migration %d apply failed", mig.id)
            break

    if not dry_run:
        conn.commit()

    return {
        "ok": error is None,
        "applied": applied,
        "skipped": skipped,
        "error": error,
        "schema_version": _current_version(conn),
    }
