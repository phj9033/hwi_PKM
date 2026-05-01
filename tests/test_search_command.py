"""Tests for `pkm search`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold(root: Path):
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\nlang: ko\n---\n\n# Alpha\n\n알파 OAuth 토큰 본문.\n",
        encoding="utf-8",
    )


def test_search_json_shape(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    res = runner.invoke(app, ["search", "OAuth", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["scope"] == "wiki"
    assert payload["results"]
    r = payload["results"][0]
    assert "scores" in r
    assert {"bm25", "vector", "rrf", "final"} <= r["scores"].keys()


def test_search_empty_index_errors(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    # Skip reindex so DB is empty
    res = runner.invoke(app, ["search", "OAuth", "--root", str(tmp_path), "--json"])
    assert res.exit_code != 0
    assert "INDEX_EMPTY" in res.output or "INDEX_EMPTY" in (res.stderr or "")


def test_search_n_limit(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    res = runner.invoke(app, ["search", "알파", "-n", "1", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert len(payload["results"]) <= 1
