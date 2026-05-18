"""m003 — add project/category/session_id columns + index.

Pure additive — no DEPENDS_ON_EXTRA. Existing rows backfill NULL.
The new columns are populated by the chunker when reading frontmatter
that contains those fields (M13 wires that up). Existing wiki/raw/writing
files have no such frontmatter → values stay NULL → search filters
classify them outside `--scope project*`.
"""

from __future__ import annotations

import sqlite3

ID = 3
DESCRIPTION = "Add project, category, session_id columns + idx_chunks_project_category"


def check(conn: sqlite3.Connection) -> bool:
    """Return True if migration is needed."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    return not ({"project", "category", "session_id"} <= cols)


def apply(conn: sqlite3.Connection) -> None:
    """Idempotent: re-applying is a no-op."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "project" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN project TEXT")
    if "category" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN category TEXT")
    if "session_id" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN session_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_project_category ON chunks(project, category)"
    )
