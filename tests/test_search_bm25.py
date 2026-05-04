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


# --- FTS5 special-character sanitization (regression tests for M2 finding) ---
#
# Natural-language queries such as `손자병법에서 도산 이란?` previously triggered
# `OperationalError: fts5: syntax error near "?"` because the question mark was
# interpreted as an FTS5 operator. _build_fts_query now phrase-quotes every
# token so any operator-like character becomes literal text.


def test_bm25_query_with_question_mark(tmp_path: Path):
    """Natural-language query ending with `?` must not error."""
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "OAuth 토큰 이란?", scope="wiki", top=5)
        # No exception is the primary contract; the OAuth hit should still surface.
        assert hits
        assert hits[0].path.endswith("oauth.md")
    finally:
        conn.close()


def test_bm25_query_with_asterisk(tmp_path: Path):
    """`*` (FTS5 prefix operator) inside a token is treated as literal."""
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # Should not raise. Match still happens via the OAuth token even though
        # `embed*` is now phrase-quoted (= literal, no prefix expansion).
        hits = query_bm25(conn, "OAuth embed*", scope="wiki", top=5)
        assert hits
    finally:
        conn.close()


def test_bm25_query_with_paren_and_colon(tmp_path: Path):
    """FTS5 grouping `(`, `)` and column qualifier `:` are neutralized."""
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # Without sanitization this would raise on `(` / `)` / `:`.
        hits = query_bm25(conn, "OAuth(token): 저장", scope="wiki", top=5)
        assert hits
    finally:
        conn.close()


def test_bm25_query_with_internal_quote(tmp_path: Path):
    """Embedded double-quote is escaped (`"` → `""`) per FTS5 phrase syntax."""
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # Should not raise — quote is doubled inside the phrase literal.
        hits = query_bm25(conn, 'OAuth "메커니즘"', scope="all", top=5)
        # Empty hits is fine; not raising is the contract.
        _ = hits
    finally:
        conn.close()


def test_bm25_query_only_specials_returns_empty_safely(tmp_path: Path):
    """Query consisting only of special characters must not error."""
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # `?` is a single token of length 1 → wrapped as `' ?'` phrase.
        # No exception, possibly zero hits.
        hits = query_bm25(conn, "???", scope="wiki", top=5)
        _ = hits
    finally:
        conn.close()
