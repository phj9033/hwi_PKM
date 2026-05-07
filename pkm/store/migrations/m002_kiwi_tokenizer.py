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

The runner's SAVEPOINT cannot be relied on for FTS5 DDL atomicity. apply()
is internally exception-safe: on failure during the swap it restores
chunks_fts_old → chunks_fts before re-raising so the runner records the
failure and skips the schema_version bump.

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
    FTS swap, restore `chunks_fts_old → chunks_fts` before re-raising."""
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
            try:
                conn.execute("DROP TABLE IF EXISTS chunks_fts")
                conn.execute("ALTER TABLE chunks_fts_old RENAME TO chunks_fts")
            except Exception:  # noqa: BLE001
                pass
        raise

    return {"rows_tokenized": len(rows)}


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    """Create the new content-table form of chunks_fts and populate it via FTS5
    'rebuild' from `chunks.text_tokenized`.

    The pre-m002 schema declared a `title UNINDEXED` column for chunks_fts,
    but it was never populated (V1 used contentless FTS5) and never read
    (search/bm25.py + reindex.py only touch `text` / rowid). Carrying it
    into the post-m002 external-content form would make `'rebuild'` try to
    read `chunks.title`, which does not exist (title lives on `documents`).
    """
    conn.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "  text_tokenized,"
        "  content=chunks,"
        "  content_rowid=id,"
        "  tokenize='unicode61'"
        ")"
    )
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
