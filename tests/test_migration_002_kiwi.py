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
    conn.execute(
        "INSERT INTO chunks_fts(rowid, text) VALUES (1, '환경설정의 인증 토큰을 저장한다')"
    )
    conn.execute(
        "INSERT INTO chunks_fts(rowid, text) VALUES "
        "(2, 'configuration of authentication token storage')"
    )
    conn.commit()


def test_apply_adds_text_tokenized_column(tmp_path: Path):
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    _seed_chunks(conn)
    mig.apply(conn)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
    assert "text_tokenized" in cols

    rows = conn.execute(
        "SELECT documents.lang, chunks.text, chunks.text_tokenized "
        "FROM chunks JOIN documents ON chunks.doc_id = documents.id "
        "ORDER BY chunks.id"
    ).fetchall()
    ko_lang, ko_text, ko_tok = rows[0]
    en_lang, en_text, en_tok = rows[1]

    assert ko_lang == "ko"
    assert en_lang == "en"
    assert ko_tok != ko_text  # segmentation happened
    assert en_tok == en_text  # English passed through


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


def test_apply_on_empty_chunks(tmp_path: Path):
    """Regression: m002 must succeed on a fresh repo with zero chunks.

    The original `_rebuild_fts` declared a `title UNINDEXED` column that did
    not exist on `chunks`, so the external-content `'rebuild'` failed with
    `no such column: T.title` even when the table was empty. A new repo
    bootstrapped via `pkm init` hits this path before its first capture.
    """
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    # No seed — chunks table is empty, mirroring `pkm bootstrap` state.

    result = mig.apply(conn)
    assert result["rows_tokenized"] == 0

    # FTS table must be queryable post-migration.
    conn.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'a OR 가'").fetchone()


def test_apply_failure_atomic_rollback(tmp_path: Path, monkeypatch):
    """If FTS rebuild fails mid-migration, original chunks_fts must remain queryable."""
    from pkm.store.migrations import m002_kiwi_tokenizer as mig

    conn = connect(tmp_path)
    _seed_chunks(conn)

    monkeypatch.setattr(
        mig, "_rebuild_fts", lambda c: (_ for _ in ()).throw(RuntimeError("forced"))
    )

    with pytest.raises(RuntimeError):
        mig.apply(conn)

    hits = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH '환경설정'"
    ).fetchall()
    assert len(hits) >= 1
