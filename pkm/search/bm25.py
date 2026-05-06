"""FTS5 BM25 search over chunks_fts.

`query_bm25(conn, query, scope, top)` returns ranked Hit rows. The `scope`
filter joins back to documents.bucket: 'wiki' / 'raw' / 'writing' / 'style' /
'all'. 'raw' covers both 'captures' and 'chunks' buckets per master spec §5.1.

Tokenizer dispatch (M12): pre-m002 repos use the FTS5 trigram tokenizer; the
``_build_fts_query`` path applies the boundary-space trick for 2-char CJK
tokens. Post-m002 repos store kiwi-pretokenized text and use FTS5 ``unicode61``,
so the query is also pre-tokenized via the same adapter and the trigram tricks
are skipped.
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


def _build_fts_query(query: str, *, trigram: bool = True) -> str:
    """Convert a user query string into an FTS5-compatible OR query.

    `trigram=True` (V1 / pre-m002): FTS5 trigram requires at least 3 Unicode
    codepoints per token. Short tokens (< 3 chars, common with 2-char CJK words
    like '토큰') cannot form a trigram on their own. We wrap them as a phrase
    with a leading space—'" 토큰"'—which matches the trigram ' 토큰' that is
    indexed for word-boundary positions.

    `trigram=False` (post-m002, kiwi pre-tokenized text + unicode61): the
    boundary-space trick is irrelevant — every kiwi morpheme is already
    whitespace-separated. Only the phrase-quote-to-neutralize-operators rule
    still applies.

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
        safe = tok.replace('"', '""')
        if trigram and len(safe) < 3:
            fts_tokens.append(f'" {safe}"')
        else:
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

    from pkm.search.tokenizer import detect_active, get_tokenizer, tokenize_for_indexing

    active = detect_active(conn)
    if active == "kiwi":
        spec = get_tokenizer(active)
        # lang='mixed' — kiwi leaves English alone (no Hangul = no segmentation).
        query = tokenize_for_indexing(query, lang="mixed", tokenizer=spec)
    fts_query = _build_fts_query(query, trigram=(active != "kiwi"))
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
