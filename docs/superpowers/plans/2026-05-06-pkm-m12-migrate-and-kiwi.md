# M12 — Migration Infra + Kiwi Tokenizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `pkm migrate` runner with a registry of versioned migration modules, then ship the first real migration (`m002_kiwi_tokenizer`) which switches FTS5 to lang-aware Kiwi pre-tokenization for improved Korean BM25 recall. Kiwi is opt-in via a new `[korean]` extra; missing extra → migration cleanly skips, schema version stays at 1, trigram remains active.

**Architecture:**
- **Registry-based runner.** Each migration is a standalone module under `pkm/store/migrations/m<NNN>_*.py` with `ID`, `DESCRIPTION`, optional `DEPENDS_ON_EXTRA`, and `check(conn)` / `apply(conn)` callables. The runner discovers modules at import time, sorts by `ID`, applies any whose `ID > schema_version`.
- **Tokenizer adapter.** `pkm/search/tokenizer.py` is the single import surface for "what tokenizer is active and how do I tokenize for it". Indexing and querying both go through it. Kiwi is loaded lazily inside the adapter; absence falls back to trigram.
- **Sidestepping FTS5's external-tokenizer C-API requirement.** SQLite's loadable Python tokenizers don't exist; rather than touching SQLite's tokenizer API, we **pre-tokenize text in Python** into a new `chunks.text_tokenized` column and let FTS5 use the `unicode61` builtin tokenizer over the pre-tokenized text. This requires both indexing and querying to apply the same tokenization function.
- **Atomic migration with full reindex of FTS only.** The migration recreates `chunks_fts` and re-populates from the pre-tokenized column. It does NOT re-embed (`docs_vec` / `chunks_vec` untouched). On failure, atomic rename reverses the swap.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), sqlite-vec (existing), kiwipiepy>=0.17 (new optional, via `[korean]` extra).

**Spec reference:** `docs/superpowers/specs/2026-05-06-pkm-v2-design.md` §5 (M12).

---

## File Structure

### Created in M12

| File | Responsibility |
|---|---|
| `pkm/store/migrations/__init__.py` | Package marker; exposes the registry helper |
| `pkm/store/migrations/_runner.py` | `discover()`, `pending(conn)`, `apply_all(conn, *, dry_run=False)` — discovers + dispatches migrations |
| `pkm/store/migrations/_registry.py` | `MigrationModule` dataclass + module-loading helpers |
| `pkm/store/migrations/m001_initial.py` | Baseline (v1) — registers ID=1 with no-op apply |
| `pkm/store/migrations/m002_kiwi_tokenizer.py` | First real migration — adds `text_tokenized` column, re-tokenizes, swaps FTS table |
| `pkm/search/tokenizer.py` | `TokenizerSpec` + `get_tokenizer()` + `detect_active(conn)` + `tokenize_for_indexing(text, lang, tokenizer)` |
| `pkm/commands/migrate.py` | `pkm migrate [--check] [--apply] [--json]` CLI |
| `tests/test_migrations_runner.py` | Unit tests for discovery, ordering, skip-on-missing-extra, dry-run |
| `tests/test_search_tokenizer.py` | Unit tests for the adapter (trigram path + kiwi path skipped if extra missing) |
| `tests/test_migrate_command.py` | CLI tests (`pkm migrate` flags + outputs) |
| `tests/test_migration_002_kiwi.py` | Integration: `m002_kiwi_tokenizer.apply()` end-to-end (slow if `[korean]` is installed; skip otherwise) |

### Modified in M12

| File | Change |
|---|---|
| `pyproject.toml` | Add `[project.optional-dependencies] korean = ["kiwipiepy>=0.17"]` |
| `pkm/cli.py` (or wherever commands are registered) | Register `pkm.commands.migrate` |
| `pkm/errors.py` | Add `PKMMigrationFailed` (`MIGRATION_FAILED`), `PKMMigrationPending` (`MIGRATION_PENDING`) |
| `pkm/commands/doctor.py` | New row: schema_version (current/latest), tokenizer (name + version). On `--strict`, fail if pending migrations exist (`MIGRATION_PENDING`). |
| `pkm/commands/reindex.py` | Use `tokenize_for_indexing` from the adapter when writing `text_tokenized` (post-migration). For pre-migration repos, stays on the existing `text` column path. |
| `pkm/search/bm25.py` | Same — query path uses the adapter. |
| `pkm/store/index_schema.py` | Document that `chunks.text_tokenized` may exist post-m002. (No schema CREATE change here — it's added by the migration via ALTER TABLE.) |
| `pkm/templates/config.toml.template` | Add `[indexing.tokenizer]` section (`preferred = "auto"`). |
| `tests/test_failure_mode_matrix.py` | Register `MIGRATION_FAILED`, `MIGRATION_PENDING` scenarios. |
| `tests/test_init.py` | Assert `[indexing.tokenizer]` is in scaffolded config. |
| `README.md` | quick-start `[ml,extract]` → `[ml,extract,korean]` (note as optional). Commands table: `pkm migrate`. Progress checkbox: M12. |
| `docs/FEATURES.md` | New §2.10 — Migrations. §2.4 (search) tokenizer note. |

---

## Pre-flight: confirm V2 baseline

- [ ] **Step 0.1: Confirm M10/M11 plans have been completed (or not blocked by them)**

M12 has no code dependency on M10/M11. It can ship at any time. Run:

```bash
uv run pytest -q
```

Expected: all tests pass before starting M12.

- [ ] **Step 0.2: Verify SQLite version + DDL-in-transaction behavior**

```bash
uv run python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

Expected: 3.35+ (any modern SQLite). The migration uses `ALTER TABLE chunks ADD COLUMN text_tokenized TEXT` and `DROP TABLE` for the FTS swap — no `DROP COLUMN` is needed (we leave `text_tokenized` in place even if migration is rolled back; the empty column is harmless).

**Important — DDL atomicity caveat**: SQLite supports DDL inside transactions, but FTS5 `CREATE VIRTUAL TABLE` writes to the schema in ways that don't always cleanly roll back through a SAVEPOINT. M12 deliberately does NOT rely on the runner's SAVEPOINT for m002's FTS swap. Instead, m002's `apply()` is **internally exception-safe**: on failure it restores `chunks_fts_old → chunks_fts` itself, then re-raises so the runner records the failure and skips the schema_version bump. See Task 5 Step 5.4 implementation.

---

## Task 1 — Two new error classes (`MIGRATION_FAILED`, `MIGRATION_PENDING`)

**Files:**
- Modify: `pkm/errors.py`
- Modify: `tests/test_failure_mode_matrix.py`

- [ ] **Step 1.1: Add failure-matrix scenarios first**

In `tests/test_failure_mode_matrix.py`, add scenarios:

```python
def _scenario_migration_failed(repo: Path) -> list[str]:
    """Force a migration to fail at apply time. We do this by setting an env
    var that the m001 module honors (a 'force-fail' switch added during this
    task). The runner should map the failure to MIGRATION_FAILED."""
    return ["migrate", "--apply", "--json"]


def _scenario_migration_pending(repo: Path) -> list[str]:
    """Manually set schema_version to 0 so the runner sees pending migrations,
    then run doctor --strict."""
    from pkm.store.index_db import connect

    conn = connect(repo)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    return ["doctor", "--strict", "--json"]
```

Register in `SCENARIOS`:

```python
    "MIGRATION_FAILED":  _scenario_migration_failed,
    "MIGRATION_PENDING": _scenario_migration_pending,
```

For `MIGRATION_FAILED`, also add to `SCENARIO_ENV`:

```python
    "MIGRATION_FAILED": {
        "PKM_TEST_FORCE_MIGRATION_FAIL": "1",
    },
```

- [ ] **Step 1.2: Run to verify failure**

```bash
uv run python -c "from pkm.errors import all_error_codes; \
  print('MIGRATION_FAILED' in all_error_codes(), \
        'MIGRATION_PENDING' in all_error_codes())"
```

Expected: `False False`.

- [ ] **Step 1.3: Add the error classes**

In `pkm/errors.py`:

```python
class PKMMigrationFailed(PKMStateError):
    """A migration's apply() raised, the runner rolled back, schema_version unchanged."""

    code = "MIGRATION_FAILED"


class PKMMigrationPending(PKMStateError):
    """schema_version < latest registered migration ID. Surfaced by `pkm doctor --strict`."""

    code = "MIGRATION_PENDING"
```

- [ ] **Step 1.4: Verify codes register**

```bash
uv run python -c "from pkm.errors import all_error_codes; \
  print('MIGRATION_FAILED' in all_error_codes(), \
        'MIGRATION_PENDING' in all_error_codes())"
```

Expected: `True True`.

- [ ] **Step 1.5: Commit**

```bash
git add pkm/errors.py tests/test_failure_mode_matrix.py
git commit -m "M12.1: PKMMigrationFailed + PKMMigrationPending error classes"
```

The matrix scenarios will fail end-to-end until Tasks 4 + 5 land. That's expected — Task 5 closes the loop.

---

## Task 2 — Migration registry + runner

**Files:**
- Create: `pkm/store/migrations/__init__.py`
- Create: `pkm/store/migrations/_registry.py`
- Create: `pkm/store/migrations/_runner.py`
- Create: `pkm/store/migrations/m001_initial.py`
- Test: `tests/test_migrations_runner.py`

- [ ] **Step 2.1: Write failing runner tests**

Create `tests/test_migrations_runner.py`:

```python
"""Tests for the M12 migration runner — discovery, ordering, skip-on-missing-extra."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pkm.store.index_db import connect
from pkm.store.migrations import _runner, _registry


def test_discover_returns_modules_sorted_by_id():
    mods = _runner.discover()
    ids = [m.id for m in mods]
    assert ids == sorted(ids)
    assert ids[0] == 1  # m001_initial


def test_pending_returns_empty_when_at_latest(tmp_path: Path):
    conn = connect(tmp_path)
    # Force schema_version to the latest registered.
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
    latest = max(m.id for m in _runner.discover())
    assert new == latest


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
    # Inject a fake migration that depends on a non-existent module.
    fake = _registry.MigrationModule(
        id=999,
        description="fake",
        depends_on_extra="this_module_definitely_does_not_exist",
        check_fn=lambda conn: {"needed": True},
        apply_fn=lambda conn: {"ok": True},
    )
    monkeypatch.setattr(_runner, "discover", lambda: [*_runner.discover(), fake])
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
    monkeypatch.setattr(_runner, "discover", lambda: [*_runner.discover(), fake])
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    initial = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    result = _runner.apply_all(conn)
    assert result["ok"] is False
    assert "boom" in (result.get("error") or "")
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    # Version must not advance past whatever m001 successfully applied. For a
    # m001-only setup, that's 1. For tests where m002+ exist, the runner stops
    # at the failed step.
    assert after >= initial
    assert after < 999
```

- [ ] **Step 2.2: Run them to verify failure**

Run: `uv run pytest tests/test_migrations_runner.py -q`
Expected: ImportError (`pkm.store.migrations` not yet created).

- [ ] **Step 2.3: Implement `_registry.py`**

```python
"""Migration module dataclass + helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationModule:
    """One registered migration, loaded from a `m<NNN>_*.py` file."""

    id: int
    description: str
    depends_on_extra: str | None
    check_fn: Callable[..., dict]
    apply_fn: Callable[..., dict]
```

- [ ] **Step 2.4: Implement `_runner.py`**

```python
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
    # `korean` → `kiwipiepy`. We register the mapping here; future extras add a row.
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
            conn.execute("ROLLBACK TO SAVEPOINT migrate_step")
            conn.execute("RELEASE migrate_step")
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
```

- [ ] **Step 2.5: Implement `m001_initial.py`**

```python
"""m001 — baseline marker for the V1 schema. No-op apply (schema is already
created by `pkm.store.index_db.connect`)."""

from __future__ import annotations

ID = 1
DESCRIPTION = "v1 baseline schema (documents, chunks, *_fts, *_vec, links)"


def check(conn) -> dict:
    return {"needed": False, "reason": "v1 schema is created by index_db.connect"}


def apply(conn) -> dict:
    return {"ok": True, "no_op": True}
```

- [ ] **Step 2.6: Create `__init__.py`**

```python
"""Migration registry + runner. See `_runner.discover()` / `apply_all()`."""

from pkm.store.migrations import _registry, _runner

__all__ = ["_registry", "_runner"]
```

- [ ] **Step 2.7: Run runner tests**

Run: `uv run pytest tests/test_migrations_runner.py -q`
Expected: PASS (7 tests).

- [ ] **Step 2.8: Commit**

```bash
git add pkm/store/migrations/ tests/test_migrations_runner.py
git commit -m "M12.2: migration runner + m001 baseline"
```

---

## Task 3 — `pkm migrate` CLI

**Files:**
- Create: `pkm/commands/migrate.py`
- Modify: `pkm/cli.py` (or wherever commands are registered)
- Test: `tests/test_migrate_command.py`

- [ ] **Step 3.1: Find the command registration site**

```bash
grep -n "register\|add_typer" /Users/user/PKM/hwi_PKM/pkm/cli.py | head -20
```

Identify the point where commands are wired (typically a sequence of `register(app)` calls). The new `pkm.commands.migrate.register(app)` will join that list.

- [ ] **Step 3.2: Write failing CLI tests**

Create `tests/test_migrate_command.py`:

```python
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
    # Dry-run should report at least m001 as a pending item with dry_run=True.
    applied_ids = [a["id"] for a in payload.get("applied", [])]
    assert 1 in applied_ids
    assert all(a.get("dry_run") for a in payload["applied"])
    # And schema_version must NOT have advanced.
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
    payload = json.loads(res.output)
    assert payload["ok"] is True
    conn = connect(tmp_path)
    after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    assert after >= 1


def test_migrate_no_pending_clean_output(tmp_path: Path):
    """Already at latest → ok, no applied items."""
    conn = connect(tmp_path)  # already at latest after init
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
```

- [ ] **Step 3.3: Run them to verify failure**

Run: `uv run pytest tests/test_migrate_command.py -q`
Expected: FAIL — `migrate` subcommand not registered.

- [ ] **Step 3.4: Implement `pkm/commands/migrate.py`**

```python
"""`pkm migrate [--check] [--apply]` — discover and apply schema migrations."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMMigrationFailed
from pkm.store.index_db import connect
from pkm.store.log import LogEvent
from pkm.store.migrations import _runner


def register(app: typer.Typer) -> None:
    @app.command("migrate")
    def migrate_cmd(
        check: bool = typer.Option(False, "--check", help="Dry-run: show pending without applying."),
        apply_now: bool = typer.Option(False, "--apply", help="Actually apply pending migrations."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Discover + apply schema migrations under `pkm/store/migrations/`."""
        # Default behavior (neither flag) is dry-run.
        do_apply = apply_now and not check

        conn = connect(root)
        try:
            result = _runner.apply_all(conn, dry_run=not do_apply)
        finally:
            conn.close()

        if result["ok"] and do_apply and result["applied"]:
            ids = ",".join(str(a["id"]) for a in result["applied"])
            post_mutation(
                root,
                LogEvent(
                    type="migrate.applied",
                    ref=ids,
                    message=f"applied migrations: {ids}",
                ),
                paths=[],
            )

        if not result["ok"]:
            err = PKMMigrationFailed(
                result.get("error") or "migration failed",
                hint="re-run with `pkm migrate --check` to see remaining work.",
            )
            payload = {"ok": False, "error": err.to_dict(), "result": result}
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"Error [{err.code}]: {err.message}", err=True)
                if err.hint:
                    typer.echo(f"  hint: {err.hint}", err=True)
            raise typer.Exit(1)

        if json_out:
            typer.echo(json.dumps({"ok": True, **result}, ensure_ascii=False))
        else:
            mode = "applying" if do_apply else "dry-run"
            typer.echo(f"migrate ({mode}):")
            for a in result["applied"]:
                marker = "(dry)" if a.get("dry_run") else ""
                typer.echo(f"  ✓ m{a['id']:03d} — {a['description']} {marker}".rstrip())
            for s in result["skipped"]:
                typer.echo(f"  · m{s['id']:03d} skipped: {s['reason']}")
            typer.echo(f"schema_version: {result['schema_version']}")
```

- [ ] **Step 3.5: Register the command**

In `pkm/cli.py`, add `from pkm.commands.migrate import register as register_migrate` (or whatever the existing convention is — match the surrounding `register_*` calls), and call `register_migrate(app)` alongside the others.

- [ ] **Step 3.6: Run CLI tests**

Run: `uv run pytest tests/test_migrate_command.py -q`
Expected: PASS (4 tests).

- [ ] **Step 3.7: Commit**

```bash
git add pkm/commands/migrate.py pkm/cli.py tests/test_migrate_command.py
git commit -m "M12.3: pkm migrate CLI — check + apply + json"
```

---

## Task 4 — Tokenizer adapter

**Files:**
- Create: `pkm/search/tokenizer.py`
- Test: `tests/test_search_tokenizer.py`

- [ ] **Step 4.1: Write failing tokenizer tests**

Create `tests/test_search_tokenizer.py`:

```python
"""Tests for pkm.search.tokenizer adapter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pkm.search import tokenizer as tk
from pkm.store.index_db import connect


def test_get_tokenizer_trigram_always_available():
    spec = tk.get_tokenizer("trigram")
    assert spec.name == "trigram"
    assert spec.available is True
    assert "trigram" in spec.fts5_create_args


def test_detect_active_returns_trigram_for_v1_schema(tmp_path: Path):
    conn = connect(tmp_path)
    assert tk.detect_active(conn) == "trigram"
    conn.close()


def test_tokenize_for_indexing_trigram_passes_through():
    spec = tk.get_tokenizer("trigram")
    out = tk.tokenize_for_indexing("hello world", lang="en", tokenizer=spec)
    # trigram path = no pre-tokenization; FTS5 handles it.
    assert out == "hello world"


def test_tokenize_for_indexing_kiwi_lang_en_passes_through():
    """Even with kiwi tokenizer, English text is passed through unchanged."""
    spec = tk.get_tokenizer("kiwi")
    if not spec.available:
        pytest.skip("kiwipiepy not installed (extra '[korean]' missing)")
    out = tk.tokenize_for_indexing("hello world", lang="en", tokenizer=spec)
    assert out == "hello world"


def test_tokenize_for_indexing_kiwi_lang_ko_segments_morphemes():
    spec = tk.get_tokenizer("kiwi")
    if not spec.available:
        pytest.skip("kiwipiepy not installed")
    out = tk.tokenize_for_indexing("환경설정의 인증 토큰", lang="ko", tokenizer=spec)
    # We expect SOME segmentation — at minimum, a token for "환경" or "설정" alone.
    # Don't over-assert specific kiwi output (it can change with model versions).
    assert " " in out
    assert len(out) >= len("환경설정의 인증 토큰")  # whitespace adds chars


def test_get_tokenizer_auto_returns_kiwi_when_available():
    spec = tk.get_tokenizer("auto")
    if tk.get_tokenizer("kiwi").available:
        assert spec.name == "kiwi"
    else:
        assert spec.name == "trigram"


def test_get_tokenizer_unknown_name_falls_back_to_trigram():
    spec = tk.get_tokenizer("nonexistent-tokenizer")
    assert spec.name == "trigram"
```

- [ ] **Step 4.2: Run them to verify failure**

Run: `uv run pytest tests/test_search_tokenizer.py -q`
Expected: ImportError.

- [ ] **Step 4.3: Implement `pkm/search/tokenizer.py`**

```python
"""Tokenizer adapter — single import surface for indexing + querying.

V1 (trigram) is the default. M12 adds kiwi via the optional `[korean]` extra.

Usage:
    spec = get_tokenizer("auto")  # honors config; kiwi if available else trigram
    text_for_fts = tokenize_for_indexing(raw_text, lang=fm.get("lang"), tokenizer=spec)

Spec reference: 2026-05-06-pkm-v2-design §5.2.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

_KIWI_MODULE = None  # lazy-loaded singleton


@dataclass(frozen=True)
class TokenizerSpec:
    name: str
    fts5_create_args: str
    available: bool
    version: str | None


def _load_kiwi():
    """Lazy-load kiwipiepy. Cached as `_KIWI_MODULE`."""
    global _KIWI_MODULE
    if _KIWI_MODULE is not None:
        return _KIWI_MODULE
    try:
        import kiwipiepy  # noqa: F401

        _KIWI_MODULE = kiwipiepy
        return _KIWI_MODULE
    except ImportError:
        return None


def get_tokenizer(name: str = "auto") -> TokenizerSpec:
    """Return the spec for a named tokenizer.

    `auto` = kiwi if importable, else trigram.
    Unknown names silently fall back to trigram.
    """
    if name == "auto":
        return get_tokenizer("kiwi" if _load_kiwi() else "trigram")
    if name == "kiwi":
        kiwi = _load_kiwi()
        version = getattr(kiwi, "__version__", None) if kiwi else None
        return TokenizerSpec(
            name="kiwi",
            fts5_create_args="tokenize='unicode61'",  # we pre-tokenize, FTS sees plain text
            available=kiwi is not None,
            version=version,
        )
    # trigram (default + fallback)
    return TokenizerSpec(
        name="trigram",
        fts5_create_args="tokenize='trigram'",
        available=True,
        version=None,
    )


def detect_active(conn: sqlite3.Connection) -> str:
    """Identify the active tokenizer from schema_version + chunks_fts metadata.

    schema_version >= 2 → kiwi (post-m002)
    Otherwise → trigram (V1).
    """
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return "trigram"
    version = int(row[0]) if row else 0
    return "kiwi" if version >= 2 else "trigram"


def tokenize_for_indexing(text: str, *, lang: str | None, tokenizer: TokenizerSpec) -> str:
    """Pre-tokenize `text` for FTS5 storage. Round-trip-safe (same input → same output)."""
    if tokenizer.name != "kiwi":
        return text  # FTS5 trigram tokenizer handles raw text
    kiwi = _load_kiwi()
    if not kiwi:
        return text  # graceful fallback if extra was uninstalled mid-session
    if lang == "en":
        return text  # English passes through; bge-m3 + the embedder side handles meaning
    # Lazy-init a single Kiwi() instance per process.
    return pretokenize_korean(text)


_KIWI_INSTANCE = None


def pretokenize_korean(text: str) -> str:
    """Run kiwi on text and join morphemes with whitespace.

    Public helper — m002_kiwi_tokenizer.apply imports this directly. Returns
    the input unchanged if kiwipiepy isn't importable (graceful fallback).
    """
    global _KIWI_INSTANCE
    kiwi = _load_kiwi()
    if not kiwi:
        return text
    if _KIWI_INSTANCE is None:
        _KIWI_INSTANCE = kiwi.Kiwi()  # type: ignore[attr-defined]
    tokens = _KIWI_INSTANCE.tokenize(text)
    # Join surface forms with spaces. We deliberately drop POS tags — FTS5 just
    # needs whitespace-separated tokens for unicode61 to index them as words.
    return " ".join(t.form for t in tokens)
```

- [ ] **Step 4.4: Run tokenizer tests**

Run: `uv run pytest tests/test_search_tokenizer.py -q`
Expected: PASS — 5 tests pass unconditionally; the 2 kiwi-specific tests skip if `[korean]` isn't installed.

- [ ] **Step 4.5: Commit**

```bash
git add pkm/search/tokenizer.py tests/test_search_tokenizer.py
git commit -m "M12.4: pkm.search.tokenizer adapter — trigram + (optional) kiwi"
```

---

## Task 5 — m002_kiwi_tokenizer migration

**Files:**
- Create: `pkm/store/migrations/m002_kiwi_tokenizer.py`
- Test: `tests/test_migration_002_kiwi.py`

- [ ] **Step 5.1: Add `[korean]` extra to pyproject**

In `pyproject.toml`, under `[project.optional-dependencies]`:

```toml
korean = ["kiwipiepy>=0.17"]
```

Run `uv sync --all-extras` to confirm the lockfile updates without conflicts (don't commit the lockfile change yet — it ships in Step 5.x).

- [ ] **Step 5.2: Write failing migration tests**

Create `tests/test_migration_002_kiwi.py`:

```python
"""Tests for m002_kiwi_tokenizer.

These are slow-leaning tests. They run only when the `korean` extra is
installed (kiwipiepy importable). On CI without the extra, the migration is
expected to skip — that case is covered by tests/test_migrations_runner.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pkm.store.index_db import connect

pytest.importorskip("kiwipiepy", reason="install with `[korean]` extra")


def _seed_chunks(conn: sqlite3.Connection):
    """Insert two documents with chunks: one Korean, one English."""
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(1,'data/wiki/concepts/k.md','wiki','K','ko','active','{}','h','2026')"
    )
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(2,'data/wiki/concepts/e.md','wiki','E','en','active','{}','h','2026')"
    )
    conn.execute(
        "INSERT INTO chunks(id,doc_id,chunk_idx,heading_path,text,token_count) "
        "VALUES (1,1,0,NULL,'환경설정의 인증 토큰을 저장한다',8)"
    )
    conn.execute(
        "INSERT INTO chunks(id,doc_id,chunk_idx,heading_path,text,token_count) "
        "VALUES (2,2,0,NULL,'configuration of authentication token storage',5)"
    )
    conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (1, '환경설정의 인증 토큰을 저장한다')")
    conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (2, 'configuration of authentication token storage')")
    conn.commit()


def test_apply_adds_text_tokenized_column(tmp_path: Path):
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    _seed_chunks(conn)
    mig.apply(conn)

    # Column added and populated
    cols = [r[1] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
    assert "text_tokenized" in cols

    rows = conn.execute(
        "SELECT lang, text, text_tokenized FROM chunks JOIN documents "
        "ON chunks.doc_id = documents.id ORDER BY chunks.id"
    ).fetchall()
    ko_lang, ko_text, ko_tok = rows[0]
    en_lang, en_text, en_tok = rows[1]

    assert ko_lang == "ko"
    assert en_lang == "en"
    # Korean: tokenized form differs from raw (segmentation happened)
    assert ko_tok != ko_text
    # English: tokenized form is the raw text (pass-through)
    assert en_tok == en_text


def test_apply_rebuilds_fts_index(tmp_path: Path):
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    _seed_chunks(conn)
    mig.apply(conn)

    # Pre-tokenized Korean text means a query for "인증" should now hit even
    # though the raw Korean had no whitespace boundary.
    hits = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH '인증'"
    ).fetchall()
    assert len(hits) >= 1


def test_apply_failure_atomic_rollback(tmp_path: Path, monkeypatch):
    """If FTS rebuild fails mid-migration, original chunks_fts must remain queryable."""
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    _seed_chunks(conn)

    # Force the rebuild step to throw.
    original = mig._rebuild_fts
    monkeypatch.setattr(
        mig, "_rebuild_fts", lambda c: (_ for _ in ()).throw(RuntimeError("forced"))
    )

    with pytest.raises(RuntimeError):
        mig.apply(conn)

    # Original FTS still works
    hits = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH '환경설정'"
    ).fetchall()
    assert len(hits) >= 1
```

- [ ] **Step 5.3: Run them to verify failure**

Run: `uv run pytest tests/test_migration_002_kiwi.py -q`
Expected: ImportError or skip if extra missing — install `[korean]` first if you want to run end-to-end:

```bash
uv pip install kiwipiepy
uv run pytest tests/test_migration_002_kiwi.py -q
```

- [ ] **Step 5.4: Implement `m002_kiwi_tokenizer.py`**

```python
"""m002 — switch FTS5 indexing to lang-aware Kiwi pre-tokenization.

Strategy (sidesteps SQLite's external-tokenizer C-API requirement):

1. ALTER TABLE chunks ADD COLUMN text_tokenized TEXT
2. For each chunk row, compute kiwi-pretokenized text (Korean/mixed) or
   pass-through (English), write to text_tokenized.
3. Rename chunks_fts → chunks_fts_old.
4. CREATE VIRTUAL TABLE chunks_fts (...) USING fts5 with content=chunks,
   indexed column = text_tokenized, tokenize='unicode61'.
5. INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild') to populate.
6. DROP TABLE chunks_fts_old.

If any step fails, SAVEPOINT rolls back the whole migration; chunks_fts_old
becomes the active chunks_fts again.

Spec reference: 2026-05-06-pkm-v2-design §5.3.
"""

from __future__ import annotations

import sqlite3

ID = 2
DESCRIPTION = "Switch chunks_fts tokenizer to lang-aware Kiwi pre-tokenization"
DEPENDS_ON_EXTRA = "korean"


def check(conn: sqlite3.Connection) -> dict:
    """Dry-run summary."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
    if "text_tokenized" in cols:
        return {"needed": False, "reason": "text_tokenized column already present"}
    n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"needed": True, "est_rows": int(n)}


def apply(conn: sqlite3.Connection) -> dict:
    """Apply migration. Internally exception-safe: on any failure during the
    FTS swap, restore `chunks_fts_old → chunks_fts` before re-raising. The
    runner's SAVEPOINT cannot be relied on for FTS5 DDL atomicity (see plan
    Step 0.2)."""
    from pkm.search.tokenizer import pretokenize_korean

    # Step 1: add column (idempotent guard)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
    if "text_tokenized" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN text_tokenized TEXT")

    # Step 2: populate text_tokenized
    rows = conn.execute(
        "SELECT chunks.id, chunks.text, documents.lang FROM chunks "
        "JOIN documents ON chunks.doc_id = documents.id"
    ).fetchall()
    for chunk_id, text, lang in rows:
        tokenized = (text or "") if lang == "en" else pretokenize_korean(text or "")
        conn.execute(
            "UPDATE chunks SET text_tokenized = ? WHERE id = ?",
            (tokenized, chunk_id),
        )

    # Step 3-5: rebuild FTS over text_tokenized — internally rollback-safe
    swap_started = False
    try:
        conn.execute("ALTER TABLE chunks_fts RENAME TO chunks_fts_old")
        swap_started = True
        _rebuild_fts(conn)

        # Verification — the new FTS must be queryable. (Spec §5.3 step 7.)
        conn.execute(
            "SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'a OR 가'"
        ).fetchone()

        # Step 6: drop old FTS table only after verification passes.
        conn.execute("DROP TABLE IF EXISTS chunks_fts_old")
    except Exception:
        if swap_started:
            # Restore: drop the (possibly partially-built) new chunks_fts
            # and rename the old one back. Best-effort; if restore itself
            # fails, the original error is preserved.
            try:
                conn.execute("DROP TABLE IF EXISTS chunks_fts")
                conn.execute("ALTER TABLE chunks_fts_old RENAME TO chunks_fts")
            except Exception:  # noqa: BLE001
                pass
        raise

    return {"rows_tokenized": len(rows)}


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    """Create the new content-table form of chunks_fts and populate it via FTS5
    'rebuild' from `chunks.text_tokenized`."""
    conn.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "  text_tokenized,"
        "  title UNINDEXED,"
        "  content=chunks,"
        "  content_rowid=id,"
        "  tokenize='unicode61'"
        ")"
    )
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
```

> Note on the FTS5 contentless-vs-content choice: the V1 schema declared `chunks_fts` as a contentless table (`content=''`). M12 changes it to a content-table that points back to `chunks` so the rebuild can pull `text_tokenized` directly. Tests in Step 5.2 verify the swap preserves query semantics.

> Note on triggers: a content-table FTS5 does NOT auto-sync on `chunks` row updates. Reindex must explicitly call `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')` ONCE at the end of its main loop (see Task 6.3). m002 is correct as-is for the migration moment; ongoing sync is reindex's job.

- [ ] **Step 5.5: Run migration tests**

Run: `uv run pytest tests/test_migration_002_kiwi.py -q`
Expected: PASS (3 tests) when `[korean]` is installed; SKIP otherwise.

- [ ] **Step 5.6: End-to-end via `pkm migrate`**

```bash
# In a temp test repo with seeded chunks (use a small fixture or the existing dev pkm repo)
cd /tmp/test-pkm-repo  # adjust as needed
uv run pkm migrate --check
uv run pkm migrate --apply
uv run pkm migrate  # second run should be a no-op
```

Expected: first run shows m002 pending → apply succeeds → second run reports schema_version=2 with no pending. If `[korean]` isn't installed, m002 skips with a "missing extra" message.

- [ ] **Step 5.7: Commit (with pyproject change)**

```bash
git add pyproject.toml uv.lock pkm/store/migrations/m002_kiwi_tokenizer.py \
        tests/test_migration_002_kiwi.py
git commit -m "M12.5: m002_kiwi_tokenizer + [korean] extra"
```

---

## Task 6 — Wire reindex + bm25 through the tokenizer adapter

**Files:**
- Modify: `pkm/commands/reindex.py`
- Modify: `pkm/search/bm25.py`
- Test: extend regression tests for both — find via `grep -rln "chunks_fts" tests/`

This task makes new reindex + search paths use `tokenize_for_indexing`. Pre-migration repos (schema_version=1) keep the trigram path identical — `detect_active` returns "trigram" and the adapter passes text through.

- [ ] **Step 6.1: Locate reindex/bm25 code**

```bash
grep -n "chunks_fts\|INSERT INTO chunks_fts" pkm/commands/reindex.py pkm/search/bm25.py
```

- [ ] **Step 6.2: Write a regression test for the adapter integration**

Add to `tests/test_search_tokenizer.py` (or a new `tests/test_reindex_tokenizer.py`):

```python
def test_reindex_uses_active_tokenizer(tmp_path: Path):
    """After m002 applied, reindex writes pre-tokenized text into chunks_fts."""
    pytest.importorskip("kiwipiepy")
    from pkm.store.index_db import connect
    from pkm.store.migrations._runner import apply_all
    from pkm.search.tokenizer import detect_active

    conn = connect(tmp_path)
    # Apply all migrations
    apply_all(conn)
    assert detect_active(conn) == "kiwi"
    conn.close()


def test_bm25_query_pretokenizes_when_kiwi_active(tmp_path: Path):
    """A Korean query goes through the same tokenizer as indexing."""
    pytest.importorskip("kiwipiepy")
    from pkm.search.tokenizer import detect_active, get_tokenizer, tokenize_for_indexing
    from pkm.store.index_db import connect
    from pkm.store.migrations._runner import apply_all

    conn = connect(tmp_path)
    apply_all(conn)
    spec = get_tokenizer(detect_active(conn))
    pre = tokenize_for_indexing("환경설정의 인증 토큰", lang="ko", tokenizer=spec)
    assert " " in pre  # tokenization produced whitespace-separated morphemes
    conn.close()
```

- [ ] **Step 6.3: Wire `tokenize_for_indexing` into reindex**

In `pkm/commands/reindex.py`, find the `INSERT INTO chunks_fts(rowid, text)` call. Branch on schema version: pre-m002 keeps the V1 path unchanged; post-m002 writes to `text_tokenized` and triggers a single FTS rebuild **after** the main loop.

Pseudocode (the actual reindex.py structure may differ — adapt to its existing function boundaries):

```python
from pkm.search.tokenizer import detect_active, get_tokenizer, tokenize_for_indexing

def _reindex_full(conn, ...):
    active = detect_active(conn)
    spec = get_tokenizer(active)
    post_m002 = active == "kiwi"

    for chunk_id, chunk_text, lang in iter_chunks(...):
        if post_m002:
            tokenized = tokenize_for_indexing(chunk_text, lang=lang, tokenizer=spec)
            conn.execute(
                "UPDATE chunks SET text_tokenized = ? WHERE id = ?",
                (tokenized, chunk_id),
            )
            # NOTE: do NOT call `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')`
            # here — it's a full rebuild; per-chunk would be O(N²). Single rebuild
            # after the loop instead.
        else:
            conn.execute(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                (chunk_id, chunk_text),
            )

    # Once after the main loop — kiwi path only.
    if post_m002:
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
```

> **Why a single end-of-loop rebuild**: a content-table FTS5 (M12 variant) doesn't auto-sync on `chunks` updates. Per-chunk `'rebuild'` would re-scan the entire table after every row update — O(N²). One rebuild at the end is O(N). Until V3 considers AFTER-INSERT/UPDATE/DELETE triggers, this end-of-loop rebuild is the simplest correct pattern.

> **Why no triggers in M12**: triggers are a separate atomic concern (must be added to chunks_fts schema *and* to migration *and* to reindex). The plan keeps M12's surface area minimal — full reindex is the only mutation path that touches `chunks` rows in the kiwi era, so a trailing rebuild covers it. If V3 adds incremental upsert paths, triggers become necessary then.

- [ ] **Step 6.4: Wire `tokenize_for_indexing` into bm25 query path**

In `pkm/search/bm25.py`, find `query_bm25(conn, q, scope, top)`. Pre-tokenize the query when kiwi is active:

```python
from pkm.search.tokenizer import detect_active, get_tokenizer, tokenize_for_indexing

active = detect_active(conn)
spec = get_tokenizer(active)
if active == "kiwi":
    q = tokenize_for_indexing(q, lang="mixed", tokenizer=spec)
# (rest of query unchanged)
```

The query passes `lang="mixed"` because we don't know the user's intent — kiwi handles mixed text by leaving English alone (no Hangul = no segmentation).

- [ ] **Step 6.5: Run regression**

Run: `uv run pytest tests/test_reindex_command.py tests/test_search_*.py tests/test_search_tokenizer.py -q`
Expected: PASS — pre-migration tests still work (trigram path unchanged), kiwi-path tests skip if extra missing.

- [ ] **Step 6.6: Commit**

```bash
git add pkm/commands/reindex.py pkm/search/bm25.py tests/test_search_tokenizer.py
git commit -m "M12.6: reindex + bm25 use tokenizer adapter (trigram unchanged, kiwi opt-in)"
```

---

## Task 7 — `pkm doctor` schema_version + tokenizer rows

**Files:**
- Modify: `pkm/commands/doctor.py`
- Test: extend `tests/test_doctor_command.py` (find with `grep -rln doctor tests/`)

- [ ] **Step 7.1: Find doctor tests**

```bash
grep -rln "test_doctor\|doctor_cmd" tests/
```

Read the closest test to understand fixture style.

- [ ] **Step 7.2: Write failing doctor tests**

Append to the chosen test file:

```python
def test_doctor_shows_schema_version(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = [it["name"] for it in payload["items"]]
    assert "schema_version" in names


def test_doctor_strict_fails_on_pending_migration(tmp_path: Path):
    """Force schema_version below latest, expect MIGRATION_PENDING under --strict."""
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    from pkm.store.index_db import connect

    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["doctor", "--strict", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 1
    payload = json.loads(res.output)
    # Either the JSON has a top-level error, or one of the items is in 'missing'/'error' state.
    assert payload["ok"] is False


def test_doctor_shows_tokenizer(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = [it["name"] for it in payload["items"]]
    assert "tokenizer" in names
```

- [ ] **Step 7.3: Run them to verify failure**

Run: `uv run pytest tests/test_doctor_command.py -q`
Expected: FAIL — doctor doesn't yet emit schema_version / tokenizer rows.

- [ ] **Step 7.4: Implement the rows**

In `pkm/commands/doctor.py`, add helper functions:

```python
def _check_schema_version(root: Path) -> _Item:
    from pkm.store.index_db import connect, schema_version
    from pkm.store.migrations._runner import discover
    try:
        conn = connect(root)
    except Exception:
        return _Item("schema_version", "missing", "no .pkm/index.db")
    try:
        current = schema_version(conn)
    finally:
        conn.close()
    latest = max((m.id for m in discover()), default=1)
    if current >= latest:
        return _Item("schema_version", "ok", f"{current}/{latest}")
    return _Item(
        "schema_version", "missing",
        f"{current}/{latest} — run `pkm migrate --apply`"
    )


def _check_tokenizer(root: Path) -> _Item:
    from pkm.store.index_db import connect
    from pkm.search.tokenizer import detect_active, get_tokenizer
    try:
        conn = connect(root)
    except Exception:
        return _Item("tokenizer", "missing", "no .pkm/index.db")
    try:
        active = detect_active(conn)
    finally:
        conn.close()
    spec = get_tokenizer(active)
    detail = f"{active}"
    if spec.version:
        detail += f" ({spec.version})"
    elif active == "trigram":
        kiwi = get_tokenizer("kiwi")
        if not kiwi.available:
            detail += " (kiwi unavailable — install `[korean]` extra to enable)"
    return _Item("tokenizer", "ok", detail)
```

In `doctor_cmd`, append both items to the list:

```python
    items.append(_check_schema_version(root))
    items.append(_check_tokenizer(root))
```

- [ ] **Step 7.5: Run doctor tests**

Run: `uv run pytest tests/test_doctor_command.py -q`
Expected: PASS.

- [ ] **Step 7.6: Verify failure-mode matrix passes**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: PASS — `MIGRATION_PENDING` and `MIGRATION_FAILED` scenarios now end-to-end work.

- [ ] **Step 7.7: Commit**

```bash
git add pkm/commands/doctor.py tests/test_doctor_command.py
git commit -m "M12.7: doctor — schema_version + tokenizer rows + --strict pending check"
```

---

## Task 8 — Config + docs + final regression

**Files:**
- Modify: `pkm/templates/config.toml.template`
- Modify: `tests/test_init.py`
- Modify: `README.md`
- Modify: `docs/FEATURES.md`

- [ ] **Step 8.1: Add `[indexing.tokenizer]` to config**

Append to `pkm/templates/config.toml.template`:

```toml
[indexing.tokenizer]
# preferred: auto | trigram | kiwi
# auto = use kiwi if `[korean]` extra is installed, else trigram.
preferred = "auto"
```

- [ ] **Step 8.2: Update init test**

In `tests/test_init.py`:

```python
def test_init_writes_indexing_tokenizer_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[indexing.tokenizer]" in cfg
    assert "preferred" in cfg
```

Run: `uv run pytest tests/test_init.py -q` → PASS.

- [ ] **Step 8.3: Update README**

In `README.md`:

- Quick-start `uv tool install -e ".[ml,extract]"` → `".[ml,extract,korean]"` (add note: "korean is optional; run without it for English-only repos").
- Commands table: add row for `Migrate | pkm migrate [--check] [--apply]`.
- Progress section: add `- [ ] M12 — Migration Infra + Kiwi`.

- [ ] **Step 8.4: Update FEATURES.md**

Add new §2.10 — Migration:

```markdown
### 2.10 Migration

- `pkm migrate [--check] [--apply]`. Default = check (dry-run).
- Each migration is a versioned module under `pkm/store/migrations/`. The
  runner discovers + sorts by ID, applies any whose ID exceeds the current
  `schema_version`. Each migration runs in its own SAVEPOINT — failure rolls
  back, version stays put.
- Migrations may declare `DEPENDS_ON_EXTRA` (e.g., `korean`). If the extra
  isn't installed, the migration is silently skipped — no error, schema
  version stays put.
- `pkm doctor` shows `schema_version: <current>/<latest>`. Under `--strict`,
  pending migrations exit with code `MIGRATION_PENDING`.

Currently registered migrations:

| ID | Description |
|----|---|
| 1  | Baseline (V1 schema) |
| 2  | Switch chunks_fts to lang-aware Kiwi pre-tokenization (requires `[korean]`) |
```

In §2.4 (Index/Search), add a paragraph about the tokenizer adapter — `auto` config, trigram default, Kiwi opt-in via `[korean]`.

- [ ] **Step 8.5: Final regression**

Run: `uv run pytest -q`
Expected: All previously-passing tests still pass; new M12 tests pass (with kiwi-specific ones skipped if `[korean]` isn't installed).

If `[korean]` is installed in your dev environment, run kiwi-specific tests too:

```bash
uv run pytest -q tests/test_migration_002_kiwi.py
```

Expected: PASS.

- [ ] **Step 8.6: Acceptance walkthrough (spec §8 V2 criteria for M12)**

- [ ] `pkm migrate --apply` works in `[korean]`-installed env
- [ ] `pkm migrate --apply` cleanly skips m002 in non-`[korean]` env (exit 0, schema_version unchanged)
- [ ] `pkm doctor` shows schema_version + tokenizer rows
- [ ] `pkm doctor --strict` fails with MIGRATION_PENDING when below latest
- [ ] Korean BM25 recall improves on at least one fixture query (slow test) — tested in Step 5.2
- [ ] English search results unchanged before/after migration (lang=en passthrough)
- [ ] Failure-mode matrix passes for `MIGRATION_FAILED` and `MIGRATION_PENDING`

- [ ] **Step 8.7: Commit + tag**

```bash
git add pkm/templates/config.toml.template tests/test_init.py README.md docs/FEATURES.md
git commit -m "M12.8: config + README + FEATURES — document migrate + tokenizer"
git tag m12-migrate-and-kiwi
git log --oneline m12-migrate-and-kiwi~10..m12-migrate-and-kiwi
```

Expected: 8 M12 commits.

---

## References

- Spec §5 — M12 design (migration infra + Kiwi)
- Spec §6.1 — error codes (MIGRATION_FAILED, MIGRATION_PENDING)
- Spec §6.2 — config (`[indexing.tokenizer]`)
- Spec §6.3 — dependencies (`[korean]` extra)
- Spec §7 — determinism (schema_version-driven tokenizer detection)
- V1 spec §5.5 — Korean processing (now extended)
- V1 spec §8.6 — Reliability + migrations (V2 closes this)

## Skills used

- @superpowers:test-driven-development — every task is test-first
- @superpowers:verification-before-completion — Step 8.6 acceptance walkthrough
- @superpowers:requesting-code-review — Task 8 + per-task reviews via subagent-driven-development
