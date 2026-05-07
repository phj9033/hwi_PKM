"""3-layer relations per spec §5.8.

Layer 1: explicit graph (`links` table — wikilinks, derived_from, tags).
Layer 2: semantic neighbors (docs_vec cosine, top-N).
Layer 3: search-time enrichment (consumed by --with-related and pkm related).

docs_vec stores a mean-pooled embedding per document, computed from its
chunk embeddings during `pkm reindex db`.  If a document has no vec row
(e.g. a capture bucket without vec_captures opted-in), semantic_neighbors
returns an empty list rather than raising.
"""

from __future__ import annotations

import sqlite3
from typing import Literal, TypedDict

Mode = Literal["backlinks", "semantic", "both"]


class RelatedBlock(TypedDict, total=False):
    wikilinks_in: list[str]
    wikilinks_out: list[str]
    derived_from: list[str]
    tags: list[str]
    semantic_neighbors: list[dict]


def related_for(
    db: sqlite3.Connection,
    path: str,
    *,
    mode: Mode = "both",
    n: int = 5,
    scope_filter: str | None = None,
) -> RelatedBlock:
    out: RelatedBlock = {}
    doc_id = _doc_id(db, path)

    if mode in ("backlinks", "both"):
        if doc_id is not None:
            out["wikilinks_out"] = _outgoing(db, doc_id, "wikilink")
            out["wikilinks_in"] = _incoming(db, doc_id, "wikilink")
            out["derived_from"] = _outgoing(db, doc_id, "derived_from")
            out["tags"] = _tags_for(db, doc_id)
    if mode in ("semantic", "both"):
        if doc_id is not None:
            out["semantic_neighbors"] = _semantic(db, doc_id, n, scope_filter=scope_filter)
    return out


def _doc_id(db: sqlite3.Connection, path: str) -> int | None:
    row = db.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
    return row[0] if row else None


def _outgoing(db: sqlite3.Connection, doc_id: int, kind: str) -> list[str]:
    rows = db.execute(
        "SELECT d2.path FROM links L "
        "JOIN documents d2 ON d2.id = L.dst_doc_id "
        "WHERE L.src_doc_id = ? AND L.kind = ?",
        (doc_id, kind),
    ).fetchall()
    return [r[0] for r in rows]


def _incoming(db: sqlite3.Connection, doc_id: int, kind: str) -> list[str]:
    rows = db.execute(
        "SELECT d1.path FROM links L "
        "JOIN documents d1 ON d1.id = L.src_doc_id "
        "WHERE L.dst_doc_id = ? AND L.kind = ?",
        (doc_id, kind),
    ).fetchall()
    return [r[0] for r in rows]


def _tags_for(db: sqlite3.Connection, doc_id: int) -> list[str]:
    """Tags are stored as kind='tag' with dst_path = tag string; dst_doc_id stays NULL."""
    rows = db.execute(
        "SELECT dst_path FROM links WHERE src_doc_id = ? AND kind = 'tag'",
        (doc_id,),
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def _semantic(
    db: sqlite3.Connection,
    doc_id: int,
    n: int,
    scope_filter: str | None = None,
) -> list[dict]:
    me = db.execute("SELECT embedding FROM docs_vec WHERE doc_id = ?", (doc_id,)).fetchone()
    if not me:
        return []
    # vec0 KNN queries require a literal LIMIT (not a parameter) and do NOT
    # support arbitrary WHERE filters or JOINs in the same statement.
    # Strategy: over-fetch generously so we can apply scope filter post-vec0.
    over = max((n + 1) * 4, 50)
    sql = f"""
        SELECT doc_id, distance
        FROM docs_vec
        WHERE embedding MATCH ?
        ORDER BY distance ASC
        LIMIT {over}
    """
    vec_rows = db.execute(sql, (me[0],)).fetchall()
    # Exclude the document itself.
    filtered = [(r[0], r[1]) for r in vec_rows if r[0] != doc_id]
    if not filtered:
        return []
    candidate_ids = [r[0] for r in filtered]
    dist_by_id = {r[0]: r[1] for r in filtered}
    placeholders = ",".join("?" for _ in candidate_ids)
    base_sql = (
        f"SELECT id, path, bucket FROM documents "
        f"WHERE id IN ({placeholders})"
    )
    params: list = list(candidate_ids)
    if scope_filter:
        # scope_filter is one of: "wiki" | "same-project:<id>" | "wiki+project:<id>"
        if scope_filter == "wiki":
            base_sql += " AND bucket = 'wiki'"
        elif scope_filter.startswith("same-project:"):
            pid = scope_filter[len("same-project:"):]
            base_sql += " AND bucket = 'projects' AND path LIKE ?"
            params.append(f"data/projects/{pid}/%")
        elif scope_filter.startswith("wiki+project:"):
            pid = scope_filter[len("wiki+project:"):]
            base_sql += " AND (bucket = 'wiki' OR (bucket = 'projects' AND path LIKE ?))"
            params.append(f"data/projects/{pid}/%")
    path_rows = db.execute(base_sql, params).fetchall()
    # Order by ascending distance, take top n.
    by_id = {r[0]: (r[1], r[2]) for r in path_rows}
    ordered = sorted(
        ((cid, d) for cid, d in filtered if cid in by_id),
        key=lambda x: x[1],
    )[:n]
    return [
        {"path": by_id[cid][0], "bucket": by_id[cid][1], "similarity": round(1.0 - float(d), 4)}
        for cid, d in ordered
    ]
