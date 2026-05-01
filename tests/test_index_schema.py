"""Tests for pkm.store.index_schema."""
from __future__ import annotations

import sqlite3

from pkm.store import index_schema


def test_schema_version_constant():
    assert index_schema.SCHEMA_VERSION == 1


def test_create_statements_apply_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    # All tables present
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','virtual')"
    )}
    assert {"documents", "chunks", "chunks_fts", "chunks_vec", "docs_vec", "links",
            "schema_version"} <= tables


def test_schema_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    # second apply must not raise (uses IF NOT EXISTS)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
