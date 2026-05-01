"""End-to-end search pipeline: BM25 + vector + RRF (M3 subset of master spec §5.4).

Stages omitted in M3 (deferred to M5):
  - [1] query expansion via AI CLI (--expand)
  - [4] cross-encoder reranking (--no-rerank flag, default ON in spec)

So the M3 search() is fully deterministic given a fixed embedder.
"""
from __future__ import annotations

import json
from pathlib import Path

from pkm.errors import PKMStateError
from pkm.search.bm25 import query_bm25
from pkm.search.rrf import rrf_fuse
from pkm.search.vector import query_vector
from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect


def _snippet(text: str, max_chars: int = 240) -> str:
    """Trim chunk text to a reasonable preview."""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _frontmatter_for(conn, doc_id: int) -> dict:
    row = conn.execute(
        "SELECT frontmatter_json, title, lang FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if not row:
        return {}
    if row["frontmatter_json"]:
        try:
            return json.loads(row["frontmatter_json"])
        except json.JSONDecodeError:
            pass
    return {"title": row["title"], "lang": row["lang"]}


def search(root: Path, query: str, *, scope: str = "wiki", n: int = 10,
           explain: bool = False) -> dict:
    """Run the full M3 search pipeline. Returns a JSON-able dict."""
    conn = connect(root)
    try:
        # Cheap empty-index probe — better error than zero results.
        cnt = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if cnt == 0:
            raise PKMStateError(
                "INDEX_EMPTY: no chunks in .pkm/index.db",
                hint="Run: pkm reindex db --full",
            )

        embedder = get_embedder()
        query_vec = embedder.embed([query])[0]

        bm25_hits = query_bm25(conn, query, scope=scope, top=50)
        vec_hits = query_vector(conn, query_vec, scope=scope, top=50)

        fused = rrf_fuse(bm25_hits, vec_hits, k=60)[:n]

        # Look up per-stage scores for each fused chunk.
        bm25_by_id = {h.chunk_id: h.score for h in bm25_hits}
        vec_by_id = {h.chunk_id: h.score for h in vec_hits}

        results: list[dict] = []
        for h in fused:
            chunk_meta = conn.execute(
                "SELECT chunk_idx, heading_path FROM chunks WHERE id = ?",
                (h.chunk_id,),
            ).fetchone()
            heading_path: list[str]
            try:
                heading_path = json.loads(chunk_meta["heading_path"]) if chunk_meta else []
            except (TypeError, json.JSONDecodeError):
                heading_path = []
            results.append({
                "path": h.path,
                "chunk_idx": chunk_meta["chunk_idx"] if chunk_meta else 0,
                "heading_path": heading_path,
                "snippet": _snippet(h.chunk_text),
                "scores": {
                    "bm25":   round(bm25_by_id.get(h.chunk_id, 0.0), 6),
                    "vector": round(vec_by_id.get(h.chunk_id, 0.0), 6),
                    "rrf":    round(h.score, 6),
                    "final":  round(h.score, 6),
                },
                "frontmatter": _frontmatter_for(conn, h.doc_id),
            })

        return {
            "ok": True,
            "query": query,
            "scope": scope,
            "results": results,
        }
    finally:
        conn.close()
