"""End-to-end search pipeline: BM25 + vector + RRF + rerank (spec §5.4).

Stage [1] query expansion via AI CLI (--expand) added in M5.7.
Stage [4] cross-encoder reranking is default ON; pass rerank=False to skip.
"""

from __future__ import annotations

import json
from pathlib import Path

from pkm.errors import PKMExpandFailed, PKMStateError
from pkm.search.bm25 import query_bm25
from pkm.search.rrf import rrf_fuse
from pkm.search.vector import query_vector
from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect


def _expand_query(root: Path, query: str) -> list[str]:
    """Expand query using AI CLI, dedup, and cap at 3 total (original + 2 variants).

    Returns [original_query, *expansion_variants] up to 3 items.
    Raises PKMExpandFailed if the AI CLI is unavailable or fails.
    """
    from pkm.llm_bridge import BridgeError, run_task

    try:
        out = run_task(root, "expand_query", query)
    except BridgeError as e:
        raise PKMExpandFailed(
            str(e),
            hint="Drop --expand or fix .pkm/config.local.toml",
        ) from e

    # Parse expansions from output (newline-separated).
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]

    # Dedup while preserving order; cap at 3 total (original first, then variants).
    seen: list[str] = []
    for q in [query, *lines]:
        if q not in seen:
            seen.append(q)
        if len(seen) >= 3:
            break
    return seen


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


def search(
    root: Path,
    query: str,
    *,
    scope: str = "wiki",
    n: int = 10,
    explain: bool = False,
    rerank: bool = True,
    expand: bool = False,
    with_related: bool = False,
) -> dict:
    """Run the full search pipeline. Returns a JSON-able dict.

    If expand=True, queries the original query + AI CLI expansions in parallel
    via BM25 and vector search, then fuses results via RRF. Reranking (if enabled)
    scores against the ORIGINAL query only.
    """
    conn = connect(root)
    try:
        # Cheap empty-index probe — better error than zero results.
        cnt = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if cnt == 0:
            raise PKMStateError(
                "INDEX_EMPTY: no chunks in .pkm/index.db",
                hint="Run: pkm reindex db --full",
            )

        # Stage [1] Query expansion (optional).
        queries = _expand_query(root, query) if expand else [query]

        embedder = get_embedder()

        # Retrieve from all queries and collect results.
        bm25_lists: list = []
        vec_lists: list = []

        for q in queries:
            bm25_hits = query_bm25(conn, q, scope=scope, top=50)
            bm25_lists.append(bm25_hits)

            query_vec = embedder.embed([q])[0]
            vec_hits = query_vector(conn, query_vec, scope=scope, top=50)
            vec_lists.append(vec_hits)

        # Stage [3] RRF fusion across all query variants — keep top 30 for the reranker.
        fused = rrf_fuse(*bm25_lists, *vec_lists, k=60)[:30]

        # Look up per-stage scores for each fused chunk (from BM25/vector of first query).
        bm25_by_id = {h.chunk_id: h.score for h in bm25_lists[0]}
        vec_by_id = {h.chunk_id: h.score for h in vec_lists[0]}

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
            results.append(
                {
                    "chunk_id": h.chunk_id,
                    "path": h.path,
                    "chunk_idx": chunk_meta["chunk_idx"] if chunk_meta else 0,
                    "heading_path": heading_path,
                    "text": h.chunk_text,
                    "snippet": _snippet(h.chunk_text),
                    "scores": {
                        "bm25": round(bm25_by_id.get(h.chunk_id, 0.0), 6),
                        "vector": round(vec_by_id.get(h.chunk_id, 0.0), 6),
                        "rrf": round(h.score, 6),
                        "final": round(h.score, 6),
                    },
                    "frontmatter": _frontmatter_for(conn, h.doc_id),
                }
            )

        # Stage [4] Cross-encoder reranking (default ON).
        # CRITICAL: Rerank uses ORIGINAL query only, not expansion variants.
        if rerank:
            from pkm.search.rerank import rerank as _rerank

            results = _rerank(query, results)
            # Update final score to reflect rerank ordering.
            for r in results:
                r["scores"]["final"] = r["scores"]["rerank"]

        final = results[:n]

        if with_related:
            from pkm.search.related import related_for

            for hit in final:
                hit["related"] = related_for(conn, hit["path"], mode="both", n=5)

        return {
            "ok": True,
            "query": query,
            "expanded": queries[1:] if expand else [],
            "scope": scope,
            "results": final,
        }
    finally:
        conn.close()
