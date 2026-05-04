"""Tests for pkm.search.sample.sample_wiki (M9)."""

from __future__ import annotations

import sqlite3

import pytest

from pkm.errors import PKMSampleInsufficientWiki
from pkm.search.sample import sample_wiki
from pkm.store.index_schema import CREATE_STATEMENTS


def _new_db() -> sqlite3.Connection:
    """Build an in-memory sqlite db with the index schema, skipping vec0 tables."""
    db = sqlite3.connect(":memory:")
    for stmt in CREATE_STATEMENTS:
        if "vec0" in stmt:
            continue
        db.executescript(stmt)
    return db


@pytest.fixture
def wiki_db_factory():
    def _build(
        n_docs: int,
        links: list[tuple[int, int]],
        unresolved_links: list[tuple[int, str]] | None = None,
    ) -> sqlite3.Connection:
        db = _new_db()
        for i in range(1, n_docs + 1):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'wiki')",
                (i, f"data/wiki/concepts/doc{i}.md"),
            )
        for src, dst in links:
            db.execute(
                "INSERT INTO links (src_doc_id, dst_doc_id, kind) VALUES (?, ?, 'wikilink')",
                (src, dst),
            )
        for src, dst_path in unresolved_links or []:
            db.execute(
                "INSERT INTO links (src_doc_id, dst_doc_id, dst_path, kind) "
                "VALUES (?, NULL, ?, 'wikilink')",
                (src, dst_path),
            )
        db.commit()
        return db

    return _build


@pytest.fixture
def wiki_db_factory_mixed():
    def _build(wiki_count: int, raw_count: int) -> sqlite3.Connection:
        db = _new_db()
        idx = 1
        for _ in range(wiki_count):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'wiki')",
                (idx, f"data/wiki/concepts/wiki{idx}.md"),
            )
            idx += 1
        for _ in range(raw_count):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'raw')",
                (idx, f"data/raw/captures/raw{idx}.md"),
            )
            idx += 1
        db.commit()
        return db

    return _build


def _doc_idx(path: str) -> int:
    """Extract the doc index from 'data/wiki/concepts/docN.md'."""
    return int(path.rsplit("/", 1)[1].removeprefix("doc").removesuffix(".md"))


def test_sample_returns_n_in_range(wiki_db_factory):
    db = wiki_db_factory(n_docs=10, links=[])
    for seed in range(20):
        result = sample_wiki(db, seed=seed)
        assert 3 <= result.n <= 5
        assert len(result.paths) == result.n
        assert result.constraint_relaxed is False


def test_sample_excludes_directly_linked(wiki_db_factory):
    # 8 docs; tight pairs (1,2) and (3,4); rest isolated. With ≥4 isolated docs
    # available, the constraint should always be satisfiable.
    db = wiki_db_factory(n_docs=8, links=[(1, 2), (3, 4)])
    forbidden_pairs = {frozenset({1, 2}), frozenset({3, 4})}
    for seed in range(50):
        result = sample_wiki(db, seed=seed)
        chosen = {_doc_idx(p) for p in result.paths}
        for a in chosen:
            for b in chosen:
                if a < b:
                    assert frozenset({a, b}) not in forbidden_pairs, (
                        f"seed={seed}: forbidden pair {a},{b} appeared "
                        f"in {sorted(chosen)} (relaxed={result.constraint_relaxed})"
                    )


def test_sample_link_constraint_works_for_reverse_direction(wiki_db_factory):
    # Insert link as (2, 1) — A→B vs B→A should be treated identically.
    db = wiki_db_factory(n_docs=8, links=[(2, 1)])
    for seed in range(30):
        result = sample_wiki(db, seed=seed)
        chosen = {_doc_idx(p) for p in result.paths}
        if 1 in chosen and 2 in chosen and not result.constraint_relaxed:
            pytest.fail(f"seed={seed}: 1+2 co-appeared without relaxation")


def test_sample_fallback_when_constraint_impossible(wiki_db_factory):
    # 3 docs all linked in a clique → cannot satisfy "not linked" for N=3 to 5.
    db = wiki_db_factory(n_docs=3, links=[(1, 2), (2, 3), (1, 3)])
    result = sample_wiki(db, seed=42)
    assert result.n == 3  # cap at pool size
    assert result.constraint_relaxed is True
    assert len(result.paths) == 3


def test_sample_caps_n_at_pool_size(wiki_db_factory):
    # Only 3 wiki docs but no links → N capped at 3 (since rng.randint(3,5) may
    # exceed 3, the function must cap to len(pool)).
    db = wiki_db_factory(n_docs=3, links=[])
    for seed in range(20):
        result = sample_wiki(db, seed=seed)
        assert result.n == 3
        assert len(result.paths) == 3


def test_sample_insufficient_wiki_raises(wiki_db_factory):
    db = wiki_db_factory(n_docs=2, links=[])
    with pytest.raises(PKMSampleInsufficientWiki) as exc:
        sample_wiki(db, seed=0)
    assert exc.value.code == "SAMPLE_INSUFFICIENT_WIKI"


def test_sample_zero_wiki_raises(wiki_db_factory):
    db = wiki_db_factory(n_docs=0, links=[])
    with pytest.raises(PKMSampleInsufficientWiki):
        sample_wiki(db, seed=0)


def test_sample_deterministic_with_seed(wiki_db_factory):
    db = wiki_db_factory(n_docs=10, links=[])
    a = sample_wiki(db, seed=123)
    b = sample_wiki(db, seed=123)
    assert a.paths == b.paths
    assert a.n == b.n


def test_sample_excludes_non_wiki_buckets(wiki_db_factory_mixed):
    db = wiki_db_factory_mixed(wiki_count=4, raw_count=4)
    for seed in range(15):
        result = sample_wiki(db, seed=seed)
        assert all(p.startswith("data/wiki/") for p in result.paths)


def test_sample_ignores_unresolved_links(wiki_db_factory):
    # Unresolved wikilinks (dst_doc_id IS NULL, only dst_path set) must not
    # affect the adjacency. With 4 unlinked wiki docs, N must always reach 3-4
    # without relaxation.
    db = wiki_db_factory(
        n_docs=4,
        links=[],
        unresolved_links=[(1, "data/wiki/concepts/missing.md")],
    )
    for seed in range(15):
        result = sample_wiki(db, seed=seed)
        assert result.constraint_relaxed is False
        assert 3 <= result.n <= 4
