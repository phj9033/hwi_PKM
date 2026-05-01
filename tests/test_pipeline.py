"""Tests for pkm.search.pipeline."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pytest

from pkm.search import pipeline
from pkm.store.embedder import StubEmbedder
from pkm.store.index_db import connect


def _seed_two_wiki(conn, embedder):
    docs = [
        ("data/wiki/a.md", "wiki", "OAuth 토큰 저장 방식 설명"),
        ("data/wiki/b.md", "wiki", "Transformer attention 메커니즘"),
    ]
    vecs = embedder.embed([d[2] for d in docs])
    for (path, bucket, text), vec in zip(docs, vecs):
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, title, lang, indexed_at) "
            "VALUES (?,?,?,?,datetime('now'))",
            (path, bucket, Path(path).stem, "ko"),
        )
        doc_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, heading_path, text, token_count) "
            "VALUES (?,0,?,?,?)",
            (doc_id, "[]", text, len(text.split())),
        )
        chunk_id = cur.lastrowid
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?,?)", (chunk_id, text))
        conn.execute("INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?,?)",
                     (chunk_id, vec.astype(np.float32).tobytes()))
    conn.commit()


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def test_pipeline_returns_spec_shape(tmp_path: Path):
    conn = connect(tmp_path)
    _seed_two_wiki(conn, StubEmbedder())
    conn.close()

    out = pipeline.search(tmp_path, "OAuth 토큰", scope="wiki", n=5)
    assert out["ok"] is True
    assert out["query"] == "OAuth 토큰"
    assert out["scope"] == "wiki"
    assert isinstance(out["results"], list)
    assert len(out["results"]) >= 1
    r = out["results"][0]
    assert {"path", "chunk_idx", "heading_path", "snippet", "scores"} <= r.keys()
    assert {"bm25", "vector", "rrf", "final"} <= r["scores"].keys()


def test_pipeline_top_n_respected(tmp_path: Path):
    conn = connect(tmp_path)
    _seed_two_wiki(conn, StubEmbedder())
    conn.close()

    out = pipeline.search(tmp_path, "메커니즘", scope="wiki", n=1)
    assert len(out["results"]) <= 1


def test_pipeline_empty_index_raises(tmp_path: Path):
    """Empty .pkm/index.db → INDEX_EMPTY error."""
    from pkm.errors import PKMStateError
    # Make the DB but seed nothing
    conn = connect(tmp_path)
    conn.close()
    with pytest.raises(PKMStateError, match="INDEX_EMPTY"):
        pipeline.search(tmp_path, "anything", scope="wiki", n=5)
