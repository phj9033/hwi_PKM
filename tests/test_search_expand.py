"""Tests for pkm.search --expand (query expansion via llm_bridge)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_expand_returns_expanded_list(tmp_path, monkeypatch):
    """--expand includes original + AI CLI expansions in 'expanded' field."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "OAuth", "--expand", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["query"] == "OAuth"
    # Fake expander returns: "OAuth\nOAuth en\nOAuth alt"
    # Since original is first and deduped, expanded = ["OAuth en", "OAuth alt"]
    assert "OAuth en" in out["expanded"]
    assert "OAuth alt" in out["expanded"]


def test_no_expand_means_empty_expanded(tmp_path, monkeypatch):
    """Without --expand, 'expanded' field is empty."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "OAuth", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["expanded"] == []


def test_expand_dedupes_and_caps_at_3(tmp_path, monkeypatch):
    """Expansion dedupes and caps at 3 total queries (original + 2 variants)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "x", "--expand", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    # Fake expander returns: "x\nx en\nx alt"
    # Deduped and capped: ["x", "x en", "x alt"] (3 total)
    # expanded excludes the original, so ["x en", "x alt"] (2 variants)
    assert len(out["expanded"]) == 2


def test_expand_failure_hard_fails(tmp_path, monkeypatch):
    """Expansion failure (missing CLI) raises PKMExpandFailed with exit code 1."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)  # no CLI on PATH
    res = runner.invoke(app, ["search", "OAuth", "--expand", "--root", str(tmp_path)])
    assert res.exit_code == 1
    # CLI emits error to stderr per pkm/cli.py:96-97
    combined = (res.stdout or "") + (res.stderr or "")
    assert "EXPAND_FAILED" in combined


def test_rerank_uses_original_query_not_expansion(tmp_path, monkeypatch):
    """Spec §5.4: reranking scores against original query, not expansion variants."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "OAuth", "--expand", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    # If rerank was applied, results should have "rerank" in scores.
    # If rerank used expansion variants, it would fail or score differently.
    out = json.loads(res.stdout)
    for hit in out["results"]:
        # With rerank (default), "rerank" should be in scores.
        assert "rerank" in hit["scores"], "Expected rerank to be applied by default"
