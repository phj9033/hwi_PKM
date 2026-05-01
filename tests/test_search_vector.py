"""Tests for pkm.search.vector."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pkm.search.vector import query_vector
from pkm.store.embedder import StubEmbedder
from pkm.store.index_db import connect


def _seed(conn, embedder):
    rows = [
        ("data/wiki/a.md", "wiki", "alpha text"),
        ("data/wiki/b.md", "wiki", "beta text"),
        ("data/raw/captures/c.md", "captures", "gamma capture"),
    ]
    vecs = embedder.embed([r[2] for r in rows])
    for (path, bucket, text), vec in zip(rows, vecs, strict=True):
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, indexed_at) VALUES (?,?,datetime('now'))",
            (path, bucket),
        )
        doc_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, text, token_count) VALUES (?,0,?,?)",
            (doc_id, text, len(text.split())),
        )
        chunk_id = cur.lastrowid
        conn.execute(
            "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, vec.astype(np.float32).tobytes()),
        )
    conn.commit()


def test_vector_top1_matches_self(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["alpha text"])[0]
        hits = query_vector(conn, query_vec, scope="wiki", top=5)
        assert hits and hits[0].path.endswith("a.md")
    finally:
        conn.close()


def test_vector_scope_excludes(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["gamma capture"])[0]
        hits_wiki = query_vector(conn, query_vec, scope="wiki", top=5)
        # The captures doc is not in wiki scope; even if its similarity is
        # highest, the bucket filter must drop it.
        assert all("captures" not in h.path for h in hits_wiki)
    finally:
        conn.close()


def test_vector_top_limit(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["x"])[0]
        hits = query_vector(conn, query_vec, scope="all", top=1)
        assert len(hits) == 1
    finally:
        conn.close()
