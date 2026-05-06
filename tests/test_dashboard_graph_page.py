"""Tests for the M10 dashboard graph page (builder + payload)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pkm.dashboard.context import _read_graph_payload, build_context
from pkm.store.index_db import connect

_DIM = 1024


def _unit(angle_rad: float, second_axis: int = 1) -> np.ndarray:
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle_rad)
    v[second_axis] = math.sin(angle_rad)
    return v


def _seed(tmp_path: Path):
    """Two wiki nodes with one wikilink + one suggested pair."""
    (tmp_path / ".pkm").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\n[[c]]\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "wiki" / "concepts" / "b.md").write_text(
        "---\nslug: b\ntitle: B\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "wiki" / "concepts" / "c.md").write_text(
        "---\nslug: c\ntitle: C\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    conn = connect(tmp_path)
    for i, slug in enumerate(("a", "b", "c"), start=1):
        conn.execute(
            "INSERT INTO documents(id, path, bucket, title, lang, status, "
            "frontmatter_json, content_hash, indexed_at) VALUES "
            "(?, ?, 'wiki', ?, 'ko', 'active', '{}', 'h', '2026')",
            (i, f"data/wiki/concepts/{slug}.md", slug.upper()),
        )
    # a→c wikilink
    conn.execute(
        "INSERT INTO links(src_doc_id, dst_doc_id, dst_path, kind) VALUES "
        "(1, 3, 'data/wiki/concepts/c.md', 'wikilink')"
    )
    # vectors: a-b are semantically close; c is unrelated
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (1, ?)", (_unit(0.0).tobytes(),))
    conn.execute(
        "INSERT INTO docs_vec(doc_id, embedding) VALUES (2, ?)",
        (_unit(math.acos(0.92)).tobytes(),),
    )
    conn.execute(
        "INSERT INTO docs_vec(doc_id, embedding) VALUES (3, ?)",
        (_unit(math.acos(0.30), second_axis=2).tobytes(),),
    )
    conn.commit()
    conn.close()


def test_payload_has_three_nodes_and_two_edge_kinds(tmp_path: Path):
    _seed(tmp_path)
    payload = _read_graph_payload(tmp_path)
    assert payload is not None
    assert payload["stats"]["node_count"] == 3

    edge_types = {e["type"] for e in payload["edges"]}
    assert "wikilink" in edge_types
    assert "suggested" in edge_types  # a-b suggested overlay


def test_payload_node_positions_are_deterministic(tmp_path: Path):
    """Same corpus → same coordinates."""
    _seed(tmp_path)
    p1 = _read_graph_payload(tmp_path)
    p2 = _read_graph_payload(tmp_path)
    assert {n["id"]: (n["x"], n["y"]) for n in p1["nodes"]} == {
        n["id"]: (n["x"], n["y"]) for n in p2["nodes"]
    }


def test_payload_no_index_returns_none(tmp_path: Path):
    """No .pkm/index.db → payload is None (page should render an 'unavailable' card)."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    assert _read_graph_payload(tmp_path) is None


def test_max_nodes_cap_trims_least_connected(tmp_path: Path):
    """Nodes beyond the cap drop, with `trimmed` counter recording how many."""
    _seed(tmp_path)
    # Tighten the cap to 2 via config override
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[dashboard.graph]\nmax_nodes = 2\n", encoding="utf-8"
    )
    payload = _read_graph_payload(tmp_path)
    assert payload["stats"]["node_count"] == 2
    assert payload["stats"]["trimmed"] >= 1
    assert payload["config"]["max_nodes"] == 2  # config plumbing wired correctly


def test_build_context_includes_graph_payload(tmp_path: Path, monkeypatch):
    """The DashboardContext now exposes graph_payload.

    `build_context` shells out via `_run_pkm_json` for `pkm lint` and `pkm doctor`;
    we monkeypatch that helper so the test stays fast and avoids depending on a
    fully-initialised PKM repo. We only care that `graph_payload` is wired through.
    """
    _seed(tmp_path)
    monkeypatch.setattr(
        "pkm.dashboard.context._run_pkm_json", lambda *a, **kw: None
    )
    ctx = build_context(tmp_path)
    assert ctx.graph_payload is not None
    assert "nodes" in ctx.graph_payload
    assert ctx.graph_payload["config"]["max_nodes"] == 1000
