"""Tests for `pkm related <path>`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()

# doc filenames are "doc{i}.md" per seed_wiki_for_search convention.
_DOC0 = "data/wiki/concepts/doc0.md"
_DOC1 = "data/wiki/concepts/doc1.md"
_DOC2 = "data/wiki/concepts/doc2.md"


def test_related_returns_backlinks(tmp_path, monkeypatch):
    """doc1 links to doc0 → doc0.wikilinks_in should include doc1 path."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["related", _DOC0, "--mode", "backlinks", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["path"] == _DOC0
    assert "wikilinks_in" in out["related"]
    assert _DOC1 in out["related"]["wikilinks_in"]


def test_related_wikilinks_out(tmp_path, monkeypatch):
    """doc1 links to doc0 → doc1.wikilinks_out should include doc0 path."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["related", _DOC1, "--mode", "backlinks", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert "wikilinks_out" in out["related"]
    assert _DOC0 in out["related"]["wikilinks_out"]


def test_related_semantic_only(tmp_path, monkeypatch):
    """--mode semantic returns semantic_neighbors and no backlink keys."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4)
    res = runner.invoke(app, ["related", _DOC0, "--mode", "semantic", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert "semantic_neighbors" in out["related"]
    assert "wikilinks_in" not in out["related"]
    assert "wikilinks_out" not in out["related"]


def test_related_invalid_mode(tmp_path, monkeypatch):
    """Invalid --mode exits with code 2."""
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["related", "x.md", "--mode", "garbage"])
    assert res.exit_code == 2


def test_related_unknown_path_returns_empty_block(tmp_path, monkeypatch):
    """An unknown document path returns ok=True with empty related block."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=2)
    res = runner.invoke(app, ["related", "data/wiki/concepts/nonexistent.md", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["related"] == {}


def test_related_default_top_n_5(tmp_path, monkeypatch):
    """Default -n 5 caps semantic_neighbors at 5 items."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=10)
    res = runner.invoke(app, ["related", _DOC0, "--mode", "semantic", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert len(out["related"].get("semantic_neighbors", [])) <= 5


def test_related_both_mode(tmp_path, monkeypatch):
    """--mode both (default) returns all 5 keys."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["related", _DOC1, "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    related = out["related"]
    assert "wikilinks_in" in related
    assert "wikilinks_out" in related
    assert "derived_from" in related
    assert "tags" in related
    assert "semantic_neighbors" in related
