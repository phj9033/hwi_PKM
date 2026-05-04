"""Random wiki-card sampling for serendipity drafts (M9).

Picks N ∈ [3, 5] wiki cards uniformly at random from the indexed wiki pool,
subject to the constraint that no two picked cards are directly wiki-linked.
If the constraint cannot be satisfied (pool too tightly clustered), it is
relaxed and `constraint_relaxed=True` is returned.

Spec reference: docs/superpowers/plans/2026-05-04-pkm-m9-blog-random.md
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass

from pkm.errors import PKMSampleInsufficientWiki

_N_MIN = 3
_N_MAX = 5


@dataclass(frozen=True)
class SampleResult:
    paths: list[str]
    n: int
    constraint_relaxed: bool


def sample_wiki(db: sqlite3.Connection, *, seed: int | None = None) -> SampleResult:
    """Pick N ∈ [3, 5] wiki cards with link-distance ≥ 2 constraint."""
    rng = random.Random(seed)

    rows = db.execute(
        "SELECT id, path FROM documents WHERE bucket = 'wiki' ORDER BY id"
    ).fetchall()
    if len(rows) < _N_MIN:
        raise PKMSampleInsufficientWiki(
            f"wiki 카드가 {_N_MIN}장 미만입니다 — 샘플링할 풀이 부족합니다 "
            f"(현재 {len(rows)}장).",
            hint="`/promote` 로 영구 메모를 늘리세요.",
        )

    paths_by_id = {r[0]: r[1] for r in rows}
    all_ids = [r[0] for r in rows]

    adj: dict[int, set[int]] = {i: set() for i in all_ids}
    link_rows = db.execute(
        "SELECT src_doc_id, dst_doc_id FROM links "
        "WHERE kind = 'wikilink' AND dst_doc_id IS NOT NULL "
        "AND src_doc_id IN (SELECT id FROM documents WHERE bucket = 'wiki') "
        "AND dst_doc_id IN (SELECT id FROM documents WHERE bucket = 'wiki')"
    ).fetchall()
    for src, dst in link_rows:
        if src in adj and dst in adj:
            adj[src].add(dst)
            adj[dst].add(src)

    n = rng.randint(_N_MIN, _N_MAX)
    if n > len(all_ids):
        n = len(all_ids)

    picked, relaxed = _pick_with_constraint(all_ids, adj, n, rng)
    return SampleResult(
        paths=[paths_by_id[i] for i in picked],
        n=len(picked),
        constraint_relaxed=relaxed,
    )


def _pick_with_constraint(
    pool: list[int], adj: dict[int, set[int]], n: int, rng: random.Random
) -> tuple[list[int], bool]:
    """Greedy: pick first uniformly, then exclude neighbors of any pick.

    Falls back to relaxed sampling if the constraint becomes infeasible.
    """
    picked: list[int] = []
    available = set(pool)
    while len(picked) < n and available:
        choice = rng.choice(sorted(available))
        picked.append(choice)
        available.discard(choice)
        available -= adj.get(choice, set())

    if len(picked) == n:
        return picked, False

    remaining = [i for i in pool if i not in picked]
    rng.shuffle(remaining)
    needed = n - len(picked)
    picked.extend(remaining[:needed])
    return picked, True
