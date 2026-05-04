"""FTS5 (trigram) BM25 search over chunks_fts.

`query_bm25(conn, query, scope, top)` returns ranked Hit rows. The `scope`
filter joins back to documents.bucket: 'wiki' / 'raw' / 'writing' / 'all'.
'raw' covers both 'captures' and 'chunks' buckets per master spec §5.1.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_RAW_BUCKETS = ("captures", "chunks")
_BUCKET_MAP: dict[str, tuple[str, ...]] = {
    "wiki": ("wiki",),
    "raw": _RAW_BUCKETS,
    "writing": ("writing",),
    "style": ("style",),                                          # M8
    "all": ("wiki", "captures", "chunks", "writing", "style"),    # M8: +style
}


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    path: str
    bucket: str
    score: float
    chunk_text: str


def _build_fts_query(query: str) -> str:
    """Convert a user query string into an FTS5 trigram-compatible OR query.

    FTS5 trigram requires at least 3 Unicode codepoints per token. Short tokens
    (< 3 chars, common with 2-char CJK words like '토큰') cannot form a trigram
    on their own.  We wrap them as a phrase with a leading space—'" 토큰"'—which
    matches the trigram ' 토큰' that is indexed for word-boundary positions.

    Every token is phrase-quoted so FTS5 operator characters embedded in the
    user's query (``?``, ``*``, ``(``, ``)``, ``:``, ``^``, ``+``, ``-``,
    ``"``) are treated as literal text instead of triggering a syntax error
    on natural-language inputs like ``손자병법에서 도산 이란?``. Internal
    double-quotes are escaped per FTS5 phrase syntax (``"`` → ``""``).

    All tokens are joined with OR so that a multi-word query hits any document
    that contains at least one of the terms.
    """
    tokens = query.split()
    fts_tokens: list[str] = []
    for tok in tokens:
        # Escape any embedded double-quotes per FTS5 phrase literal syntax.
        safe = tok.replace('"', '""')
        if len(safe) < 3:
            # Leading space tags into the boundary trigram for 2-char CJK words.
            fts_tokens.append(f'" {safe}"')
        else:
            # Phrase-quote to neutralize FTS5 operators (?, *, (, ), :, ^, +, -).
            fts_tokens.append(f'"{safe}"')
    return " OR ".join(fts_tokens)


def query_bm25(
    conn: sqlite3.Connection, query: str, scope: str = "wiki", top: int = 50
) -> list[Hit]:
    if not query.strip():
        return []
    buckets = _BUCKET_MAP.get(scope)
    if buckets is None:
        raise ValueError(f"unknown scope: {scope!r}")
    placeholders = ",".join("?" for _ in buckets)
    fts_query = _build_fts_query(query)
    sql = f"""
        SELECT c.id AS chunk_id, c.doc_id AS doc_id, d.path AS path,
               d.bucket AS bucket, c.text AS text,
               bm25(chunks_fts) AS raw_score
        FROM chunks_fts
        JOIN chunks    c ON c.id      = chunks_fts.rowid
        JOIN documents d ON d.id      = c.doc_id
        WHERE chunks_fts MATCH ?
          AND d.bucket IN ({placeholders})
        ORDER BY bm25(chunks_fts) ASC
        LIMIT ?
    """
    params = (fts_query, *buckets, top)
    rows = conn.execute(sql, params).fetchall()
    return [
        Hit(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            path=row["path"],
            bucket=row["bucket"],
            score=-float(row["raw_score"]),
            chunk_text=row["text"],
        )
        for row in rows
    ]
