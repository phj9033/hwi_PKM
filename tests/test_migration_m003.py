"""Tests for m003 — adds project, category, session_id columns + index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pkm.store.index_db import connect
from pkm.store.migrations import _runner
from pkm.store.migrations.m003_project_scope import ID, apply, check


def test_m003_id_is_3():
    assert ID == 3


def test_m003_check_returns_true_when_columns_missing(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    assert check(conn) is True


def test_m003_apply_adds_three_columns_and_index(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    apply(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    assert {"project", "category", "session_id"} <= cols
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(chunks)")}
    assert "idx_chunks_project_category" in indexes


def test_m003_apply_is_idempotent(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    apply(conn)
    # Second call must not raise
    apply(conn)


def test_m003_existing_chunks_have_null_project(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(1,'data/wiki/concepts/x.md','wiki','X','en','active','{}','h','2026')"
    )
    conn.execute(
        "INSERT INTO chunks(id,doc_id,chunk_idx,heading_path,text,token_count) "
        "VALUES (1,1,0,NULL,'body',1)"
    )
    conn.commit()
    apply(conn)
    row = conn.execute(
        "SELECT project, category, session_id FROM chunks WHERE id=1"
    ).fetchone()
    assert tuple(row) == (None, None, None)


def test_m003_runs_via_runner(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    pending = _runner.pending(conn)
    ids = [m.id for m in pending]
    assert 3 in ids
    _runner.apply_all(conn)
    v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert v >= 3
