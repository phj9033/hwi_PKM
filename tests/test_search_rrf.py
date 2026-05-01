"""Tests for pkm.search.rrf."""
from __future__ import annotations

from pkm.search.bm25 import Hit
from pkm.search.rrf import rrf_fuse


def _h(chunk_id, score=0.0):
    return Hit(chunk_id=chunk_id, doc_id=chunk_id, path=f"p{chunk_id}",
               bucket="wiki", score=score, chunk_text="t")


def test_empty_inputs_return_empty():
    assert rrf_fuse() == []
    assert rrf_fuse([], []) == []


def test_single_list_preserves_order():
    listA = [_h(1), _h(2), _h(3)]
    fused = rrf_fuse(listA, k=60)
    assert [h.chunk_id for h in fused] == [1, 2, 3]


def test_two_lists_overlapping_doc_ranks_first():
    # listA: 1, 2; listB: 3, 1 → doc 1 hits both lists → highest fused score
    fused = rrf_fuse([_h(1), _h(2)], [_h(3), _h(1)], k=60)
    assert fused[0].chunk_id == 1


def test_k_constant():
    """Higher k flattens differences; lower k sharpens them. Just verify monotonicity."""
    listA = [_h(1), _h(2)]
    listB = [_h(2), _h(1)]
    fused_low_k = rrf_fuse(listA, listB, k=1)
    fused_high_k = rrf_fuse(listA, listB, k=1000)
    # Both should produce the same ordering (a tie because each doc shows in both)
    # but the score values differ. The function should not crash and return all docs.
    assert len(fused_low_k) == 2
    assert len(fused_high_k) == 2


def test_score_is_sum_of_reciprocal_ranks():
    listA = [_h(1)]            # doc 1 rank 1 → 1/(60+1)
    listB = [_h(1)]            # doc 1 rank 1 → 1/(60+1)
    fused = rrf_fuse(listA, listB, k=60)
    assert abs(fused[0].score - (2.0 / 61.0)) < 1e-9
