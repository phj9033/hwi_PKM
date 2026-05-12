"""Tests for `pkm search --with-related`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_with_related_adds_block_per_hit(tmp_path, monkeypatch):
    """--with-related attaches a 'related' block to every hit."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["search", "test", "--with-related", "--no-rerank", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert len(out["results"]) > 0
    for hit in out["results"]:
        assert "related" in hit


def test_without_with_related_no_block(tmp_path, monkeypatch):
    """Without --with-related, hits have no 'related' key."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "test", "--no-rerank", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "related" not in hit


def test_with_related_text_output(tmp_path, monkeypatch):
    """--with-related works in plain-text mode without errors."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=2, with_links=True)
    res = runner.invoke(app, ["search", "test", "--with-related", "--no-rerank", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output


def test_with_related_wikilinks_in_populated(tmp_path, monkeypatch):
    """When with_links=True, doc0 should appear as wikilinks_in for at least one hit."""
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["search", "test", "--with-related", "--no-rerank", "--json", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    # doc0 is linked-to by doc1, doc1 by doc2, etc.
    # At least some hit should have a non-empty wikilinks_in or wikilinks_out.
    any_link = any(
        hit["related"].get("wikilinks_in") or hit["related"].get("wikilinks_out")
        for hit in out["results"]
    )
    assert any_link, "Expected at least one hit to have wikilinks populated"
