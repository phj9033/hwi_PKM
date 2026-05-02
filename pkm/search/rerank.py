"""bge-reranker-v2-m3 cross-encoder integration.

Default-ON stage [4] of the pipeline (spec §5.4). Loads the reranker lazily
on first call so `pkm --help` and tests that don't exercise rerank stay
sub-second. Test-time stub: PKM_TEST_STUB_RERANKER=1 returns scores
derived from chunk_id (descending) — deterministic and dependency-free.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pkm.errors import PKMRerankModelMissing

_REPO = "BAAI/bge-reranker-v2-m3"
_CACHED = None  # cached CrossEncoder instance


def _stub_score(query: str, chunk_id: int) -> float:
    """Deterministic test score: higher chunk_id = higher rerank."""
    return float(chunk_id) / 10000.0


def rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds a `scores.rerank` field to each candidate, sorted by it desc.

    `candidates` is the post-RRF list shape from pipeline.py.
    """
    if os.environ.get("PKM_TEST_STUB_RERANKER") == "1":
        for c in candidates:
            c["scores"]["rerank"] = _stub_score(query, c.get("chunk_id", 0))
    else:
        model = _load()
        pairs = [(query, c["text"]) for c in candidates]
        scores = model.predict(pairs)
        for c, s in zip(candidates, scores, strict=False):
            c["scores"]["rerank"] = float(s)

    candidates.sort(key=lambda c: c["scores"]["rerank"], reverse=True)
    return candidates


def _load():
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    cache = Path.home() / ".cache" / "pkm" / "models" / _REPO.replace("/", "__")
    if not cache.exists() or not any(cache.iterdir()):
        raise PKMRerankModelMissing(
            f"Reranker not found at {cache}.",
            hint="Run `pkm doctor --download` (or pass --no-rerank).",
        )
    from sentence_transformers import CrossEncoder

    _CACHED = CrossEncoder(str(cache))
    return _CACHED
