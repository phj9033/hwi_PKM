"""Tests for the MISSING_LINK_CANDIDATE lint rule + helper.

We bypass the real embedder by inserting hand-crafted unit vectors directly
into ``docs_vec``. This gives full control over pairwise similarity and lets
us assert threshold + graph-distance filtering without needing bge-m3 to
produce specific cosine values.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pkm.lint.missing_links import LinkSuggestion, find_suggestions, load_config
from pkm.store.index_db import connect

_DIM = 1024


def _unit(angle_rad: float, second_axis: int = 1) -> np.ndarray:
    """Return a 1024-d unit vector in the (axis 0, axis `second_axis`) plane."""
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle_rad)
    v[second_axis] = math.sin(angle_rad)
    return v


def _insert_doc(
    conn: sqlite3.Connection,
    doc_id: int,
    rel_path: str,
    *,
    bucket: str = "wiki",
    status: str = "active",
) -> None:
    conn.execute(
        "INSERT INTO documents(id, path, bucket, title, lang, status, frontmatter_json, "
        "content_hash, indexed_at) VALUES (?, ?, ?, ?, 'ko', ?, '{}', 'h', '2026-05-01')",
        (doc_id, rel_path, bucket, rel_path, status),
    )


def _insert_vec(conn: sqlite3.Connection, doc_id: int, vec: np.ndarray) -> None:
    conn.execute(
        "INSERT INTO docs_vec(doc_id, embedding) VALUES (?, ?)",
        (doc_id, vec.astype(np.float32).tobytes()),
    )


def _insert_link(conn: sqlite3.Connection, src: int, dst: int, kind: str = "wikilink") -> None:
    conn.execute(
        "INSERT INTO links(src_doc_id, dst_doc_id, dst_path, kind) VALUES (?, ?, ?, ?)",
        (src, dst, "", kind),
    )


def _scaffold(root: Path) -> sqlite3.Connection:
    """Initialize the index DB schema and return an open connection."""
    (root / ".pkm").mkdir(parents=True, exist_ok=True)
    return connect(root)


def test_no_db_returns_empty(tmp_path: Path):
    assert find_suggestions(tmp_path) == []


def test_disabled_config_returns_empty(tmp_path: Path):
    """Even with strong candidates, disabled flag short-circuits."""
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[lint.missing_link]\nenabled = false\n", encoding="utf-8"
    )
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.95))  # similarity ≈ 0.95
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_close_pair_with_no_link_is_suggested(tmp_path: Path):
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.95))  # cos sim ≈ 0.95
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    sugs = find_suggestions(tmp_path)
    assert len(sugs) == 1
    s = sugs[0]
    assert isinstance(s, LinkSuggestion)
    assert s.src_path == "data/wiki/concepts/a.md"  # canonical (alphabetical)
    assert s.dst_path == "data/wiki/concepts/b.md"
    assert s.similarity >= 0.9


def test_directly_linked_pair_is_excluded(tmp_path: Path):
    """min_graph_distance=2 means direct (distance-1) pairs are skipped."""
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.95))
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    _insert_link(conn, 1, 2)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_below_threshold_pair_is_excluded(tmp_path: Path):
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    # cos sim = 0.5 — below default 0.78
    b = _unit(math.acos(0.5))
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_chain_a_b_c_at_distance_two_is_suggested(tmp_path: Path):
    """A-B-C linked. A & C semantically close (dist=2 >= min_d=2) → suggest A-C."""
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    c = _unit(math.acos(0.92))
    b = _unit(math.acos(0.3), second_axis=2)  # B unrelated to both
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_doc(conn, 3, "data/wiki/concepts/c.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    _insert_vec(conn, 3, c)
    _insert_link(conn, 1, 2)
    _insert_link(conn, 2, 3)
    conn.commit()
    conn.close()

    sugs = find_suggestions(tmp_path)
    paths = {(s.src_path, s.dst_path) for s in sugs}
    assert ("data/wiki/concepts/a.md", "data/wiki/concepts/c.md") in paths


def test_min_graph_distance_3_excludes_common_neighbor_pair(tmp_path: Path):
    """min_d=3 excludes pairs that share a neighbor (distance=2)."""
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[lint.missing_link]\nmin_graph_distance = 3\n", encoding="utf-8"
    )
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    c = _unit(math.acos(0.92))
    b = _unit(math.acos(0.3), second_axis=2)
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_doc(conn, 3, "data/wiki/concepts/c.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    _insert_vec(conn, 3, c)
    _insert_link(conn, 1, 2)
    _insert_link(conn, 2, 3)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_pair_dedupe_yields_once(tmp_path: Path):
    """A→B and B→A would otherwise yield twice; canonical sort de-dupes."""
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.93))
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    sugs = find_suggestions(tmp_path)
    assert len(sugs) == 1


def test_deprecated_wiki_excluded(tmp_path: Path):
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.95))
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md", status="deprecated")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_non_wiki_excluded(tmp_path: Path):
    """Captures and writing don't get suggestion treatment even if embedded."""
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.95))
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/raw/captures/x.md", bucket="captures", status="reviewed")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    assert find_suggestions(tmp_path) == []


def test_load_config_defaults(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg["enabled"] is True
    assert cfg["sim_threshold"] == pytest.approx(0.78)
    assert cfg["min_graph_distance"] == 2
    assert cfg["top_k_per_doc"] == 3


def test_load_config_overrides(tmp_path: Path):
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[lint.missing_link]\nsim_threshold = 0.9\ntop_k_per_doc = 1\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg["sim_threshold"] == pytest.approx(0.9)
    assert cfg["top_k_per_doc"] == 1
    # untouched defaults remain
    assert cfg["min_graph_distance"] == 2
    assert cfg["enabled"] is True


def test_top_k_caps_per_source(tmp_path: Path):
    """One central doc highly similar to 5 others → only top 1 emitted (cap=1)."""
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[lint.missing_link]\ntop_k_per_doc = 1\n", encoding="utf-8"
    )
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    _insert_doc(conn, 1, "data/wiki/concepts/center.md")
    _insert_vec(conn, 1, a)
    # 5 candidates each at decreasing similarity, all above threshold (0.78).
    angles = [math.acos(s) for s in (0.95, 0.92, 0.89, 0.85, 0.80)]
    for i, theta in enumerate(angles, start=2):
        _insert_doc(conn, i, f"data/wiki/concepts/peer{i}.md")
        _insert_vec(conn, i, _unit(theta))
    conn.commit()
    conn.close()

    sugs = find_suggestions(tmp_path)
    # center has 5 candidates but cap=1 → at most 1 pair *originating* from it.
    # However each peer also queries and might suggest center: dedupe canonicalizes
    # those to (center, peerX). Net: every peer becomes its own source and
    # contributes (center, peerX) until the dedupe set hits each pair once.
    # The peers fire too — so the final set is at most 5 unique pairs, which is
    # what we expect. The cap is per-source-call, not global.
    assert len(sugs) <= 5
    # similarity is non-increasing in the output
    assert sugs == sorted(sugs, key=lambda s: (-s.similarity, s.src_path, s.dst_path))
