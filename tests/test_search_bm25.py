"""Tests for pkm.search.bm25."""

from __future__ import annotations

from pathlib import Path

from pkm.search.bm25 import query_bm25
from pkm.store.index_db import connect


def _seed_three_docs(conn):
    """Seed 3 docs in different buckets with deterministic chunks."""
    rows = [
        ("data/wiki/concepts/oauth.md", "wiki", "OAuth 토큰 저장 방식"),
        ("data/wiki/concepts/transformer.md", "wiki", "Transformer attention 메커니즘"),
        ("data/raw/captures/foo.md", "captures", "BM25 RRF 융합 논문 요약"),
    ]
    for path, bucket, text in rows:
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, indexed_at) VALUES (?,?,datetime('now'))",
            (path, bucket),
        )
        doc_id = cur.lastrowid
        conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, text, token_count) VALUES (?,0,?,?)",
            (doc_id, text, len(text.split())),
        )
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)", (chunk_id, text))
    conn.commit()


def test_bm25_finds_korean_term(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "OAuth", scope="wiki", top=5)
        assert hits
        assert hits[0].path.endswith("oauth.md")
    finally:
        conn.close()


def test_bm25_scope_filter(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # "BM25" only appears in captures; with scope=wiki should miss
        hits_wiki = query_bm25(conn, "BM25", scope="wiki", top=5)
        hits_raw = query_bm25(conn, "BM25", scope="raw", top=5)
        assert hits_wiki == []
        assert hits_raw and "captures" in hits_raw[0].path
    finally:
        conn.close()


def test_bm25_scope_all(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "토큰", scope="all", top=5)
        assert hits  # at least the wiki/oauth.md hit
    finally:
        conn.close()


def test_bm25_top_limit(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "메커니즘 attention 토큰 RRF", scope="all", top=2)
        assert len(hits) <= 2
    finally:
        conn.close()
