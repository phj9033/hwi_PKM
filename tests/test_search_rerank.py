"""Tests for pkm.search.rerank — cross-encoder reranking stage."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.search import rerank as rerank_mod

runner = CliRunner()


def _seed(tmp_path):
    from tests._helpers import seed_wiki_for_search

    seed_wiki_for_search(tmp_path, n=5)


def test_default_search_applies_rerank_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    res = runner.invoke(app, ["search", "test", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "rerank" in hit["scores"]


def test_no_rerank_skips_stage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    res = runner.invoke(app, ["search", "test", "--no-rerank", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "rerank" not in hit["scores"]


def test_stub_score_is_deterministic():
    s1 = rerank_mod._stub_score("q", 42)
    s2 = rerank_mod._stub_score("q", 42)
    assert s1 == s2 == 42 / 10000.0


def test_stub_orders_by_chunk_id_desc():
    cands = [
        {"path": "a.md", "chunk_idx": 0, "chunk_id": 1, "text": "x", "scores": {}},
        {"path": "b.md", "chunk_idx": 0, "chunk_id": 9, "text": "y", "scores": {}},
        {"path": "c.md", "chunk_idx": 0, "chunk_id": 5, "text": "z", "scores": {}},
    ]
    out = rerank_mod.rerank("q", cands)
    assert [c["chunk_id"] for c in out] == [9, 5, 1]


def test_missing_model_raises_pkm_error(monkeypatch):
    monkeypatch.delenv("PKM_TEST_STUB_RERANKER", raising=False)
    monkeypatch.setattr(rerank_mod, "_CACHED", None)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    from pkm.errors import PKMRerankModelMissing

    with pytest.raises(PKMRerankModelMissing) as ei:
        rerank_mod._load()
    assert ei.value.code == "RERANK_MODEL_MISSING"


def test_search_cli_hard_fails_on_missing_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    monkeypatch.delenv("PKM_TEST_STUB_RERANKER", raising=False)
    monkeypatch.setattr(rerank_mod, "_CACHED", None)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    res = runner.invoke(app, ["search", "test", "--root", str(tmp_path)])
    assert res.exit_code == 1
    combined = (res.stdout or "") + (res.stderr or "")
    assert "RERANK_MODEL_MISSING" in combined
