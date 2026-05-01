"""Reciprocal Rank Fusion across multiple ranked Hit lists.

score(d) = Σ_lists 1 / (k + rank_in_list(d)),  rank starts at 1.

The fused result keeps the first Hit metadata seen for each chunk_id (path,
bucket, chunk_text). The original per-list scores are intentionally NOT
re-attached here — `pipeline.search()` does that lookup so we don't lose
either signal in the fused output.
"""
from __future__ import annotations

from collections.abc import Sequence

from pkm.search.bm25 import Hit


def rrf_fuse(*ranked_lists: Sequence[Hit], k: int = 60) -> list[Hit]:
    scored: dict[int, float] = {}
    first_seen: dict[int, Hit] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scored[hit.chunk_id] = scored.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            if hit.chunk_id not in first_seen:
                first_seen[hit.chunk_id] = hit

    fused: list[Hit] = []
    for chunk_id, score in scored.items():
        base = first_seen[chunk_id]
        fused.append(Hit(
            chunk_id=base.chunk_id,
            doc_id=base.doc_id,
            path=base.path,
            bucket=base.bucket,
            score=score,
            chunk_text=base.chunk_text,
        ))
    fused.sort(key=lambda h: h.score, reverse=True)
    return fused
