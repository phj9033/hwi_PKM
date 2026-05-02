"""Tests for `pkm reindex db`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold(root: Path):
    """Minimal pkm tree with one wiki doc and one capture."""
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "raw" / "captures").mkdir(parents=True)
    (root / ".pkm").mkdir()
    (root / "data" / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\nlang: ko\n---\n\n# Alpha\n\n알파 본문.\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "captures" / "2026-05-01-bm25.md").write_text(
        "---\ntitle: bm25\nslug: 2026-05-01-bm25\nlang: en\nstatus: draft\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "# BM25\n\nBM25 RRF paper notes.\n",
        encoding="utf-8",
    )


def test_reindex_full_creates_db_and_rows(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] >= 2

    conn = connect(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] >= 2
        # wiki doc has a vec row; capture (default config) does not
        wiki_id = conn.execute("SELECT id FROM documents WHERE bucket='wiki'").fetchone()[0]
        cap_id = conn.execute("SELECT id FROM documents WHERE bucket='captures'").fetchone()[0]
        wiki_vec = conn.execute(
            "SELECT COUNT(*) FROM chunks_vec WHERE chunk_id IN "
            "(SELECT id FROM chunks WHERE doc_id=?)",
            (wiki_id,),
        ).fetchone()[0]
        cap_vec = conn.execute(
            "SELECT COUNT(*) FROM chunks_vec WHERE chunk_id IN "
            "(SELECT id FROM chunks WHERE doc_id=?)",
            (cap_id,),
        ).fetchone()[0]
        assert wiki_vec >= 1
        assert cap_vec == 0
    finally:
        conn.close()


def test_reindex_incremental_skips_unchanged(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    # Re-run incremental — nothing changed
    res = runner.invoke(app, ["reindex", "db", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["stats"]["documents_indexed"] == 0
    assert payload["stats"]["documents_skipped"] == 2


def test_reindex_single_path(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    target = tmp_path / "data" / "wiki" / "concepts" / "alpha.md"
    res = runner.invoke(app, ["reindex", "db", str(target), "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] == 1


def test_reindex_scope_wiki_only(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        app, ["reindex", "db", "--scope", "wiki", "--root", str(tmp_path), "--full", "--json"]
    )
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] == 1  # only wiki
