"""SQLite + sqlite-vec schema for the search index.

Master spec §5.2. Schema version 1 is the initial M3 schema. Any future
breaking change bumps SCHEMA_VERSION and adds a migration step in index_db.

All CREATE statements use IF NOT EXISTS so re-applying is a no-op.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

CREATE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY,
      path TEXT UNIQUE NOT NULL,
      bucket TEXT NOT NULL,
      title TEXT,
      lang TEXT,
      status TEXT,
      source_url TEXT,
      frontmatter_json TEXT,
      content_hash TEXT,
      indexed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
      id INTEGER PRIMARY KEY,
      doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_idx INTEGER NOT NULL,
      heading_path TEXT,
      text TEXT NOT NULL,
      token_count INTEGER
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
      text,
      title UNINDEXED,
      content='',
      tokenize='trigram'
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
      chunk_id INTEGER PRIMARY KEY,
      embedding FLOAT[1024]
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS docs_vec USING vec0(
      doc_id INTEGER PRIMARY KEY,
      embedding FLOAT[1024]
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS links (
      src_doc_id INTEGER NOT NULL,
      dst_doc_id INTEGER,
      dst_path TEXT,
      kind TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    )
    """,
)
