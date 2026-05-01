"""SQLite + sqlite-vec connection helper for the search index.

`connect(root)` opens (creating if needed) `<root>/.pkm/index.db`, loads the
sqlite-vec loadable extension, and applies the schema if it isn't there yet.
The schema is idempotent (all CREATE statements use IF NOT EXISTS).

Heavy imports (`sqlite_vec`) are inside functions so importing this module
does not pull in the native extension.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from pkm.store import index_schema


def _db_path(root: Path) -> Path:
    return root / ".pkm" / "index.db"


def connect(root: Path) -> sqlite3.Connection:
    """Open `<root>/.pkm/index.db` with sqlite-vec extension loaded.

    Creates the directory + file if needed and applies the schema on first
    connect. Idempotent on re-open.
    """
    db = _db_path(root)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.enable_load_extension(True)
    import sqlite_vec  # lazy
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    if schema_version(conn) < index_schema.SCHEMA_VERSION:
        init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply CREATE TABLE statements + record schema_version. Idempotent."""
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    # Insert version row only if not present
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    if cur.fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                     (index_schema.SCHEMA_VERSION,))
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    """Return current schema_version row, or 0 if uninitialized."""
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0
