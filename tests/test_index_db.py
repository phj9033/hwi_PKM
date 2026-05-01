"""Tests for pkm.store.index_db."""
from __future__ import annotations

from pathlib import Path

from pkm.store import index_db


def test_connect_creates_db_dir(tmp_path: Path):
    conn = index_db.connect(tmp_path)
    try:
        assert (tmp_path / ".pkm" / "index.db").exists()
        assert index_db.schema_version(conn) == 1
    finally:
        conn.close()


def test_connect_loads_sqlite_vec(tmp_path: Path):
    conn = index_db.connect(tmp_path)
    try:
        version = conn.execute("SELECT vec_version()").fetchone()
        assert version is not None
    finally:
        conn.close()


def test_connect_idempotent(tmp_path: Path):
    conn1 = index_db.connect(tmp_path)
    conn1.close()
    # second connect on existing DB must keep schema_version
    conn2 = index_db.connect(tmp_path)
    try:
        assert index_db.schema_version(conn2) == 1
    finally:
        conn2.close()


def test_schema_version_zero_on_empty(tmp_path: Path):
    """A bare DB without init_schema reports version 0."""
    import sqlite3
    db = tmp_path / ".pkm" / "index.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    try:
        assert index_db.schema_version(conn) == 0
    finally:
        conn.close()
