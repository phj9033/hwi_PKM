"""Cosine vector search over chunks_vec (sqlite-vec vec0).

Vectors are stored already L2-normalized (RealEmbedder normalizes; StubEmbedder
normalizes). Cosine distance = 1 - cos(θ); smaller is better.

We post-filter by bucket (joining back to documents) rather than partitioning
the vec0 table. For thousands of chunks this is fast enough; if it ever
becomes a bottleneck, add a per-bucket vec0 partition in M3.x.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from pkm.search.bm25 import _BUCKET_MAP, Hit, _resolve_scope_filter


def query_vector(
    conn: sqlite3.Connection, query_vec: np.ndarray, scope: str = "wiki", top: int = 50
) -> list[Hit]:
    if query_vec.ndim != 1:
        query_vec = query_vec.reshape(-1)

    where_clause, where_params = _resolve_scope_filter(scope)

    # Fetch a wider top from vec0, then scope-filter (robust + simple).
    over_fetch = max(top * 4, 200)
    sql_vec = f"""
        SELECT chunk_id, distance
        FROM chunks_vec
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT {int(over_fetch)}
    """
    vec_blob = query_vec.astype(np.float32).tobytes()
    vec_rows = conn.execute(sql_vec, (vec_blob,)).fetchall()
    if not vec_rows:
        return []

    chunk_ids = [r["chunk_id"] for r in vec_rows]
    dist_by_id = {r["chunk_id"]: float(r["distance"]) for r in vec_rows}

    sql_meta = f"""
        SELECT c.id AS chunk_id, c.doc_id AS doc_id, c.text AS text,
               d.path AS path, d.bucket AS bucket
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        WHERE c.id IN ({",".join("?" for _ in chunk_ids)})
          AND {where_clause}
    """
    meta_rows = conn.execute(sql_meta, (*chunk_ids, *where_params)).fetchall()

    hits: list[Hit] = [
        Hit(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            path=row["path"],
            bucket=row["bucket"],
            score=1.0 - dist_by_id[row["chunk_id"]],  # → similarity, higher better
            chunk_text=row["text"],
        )
        for row in meta_rows
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top]
