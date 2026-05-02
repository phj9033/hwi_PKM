"""Golden snapshot tests for `pkm search` over the Korean fixture corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from tests.fixtures.korean_corpus import install_corpus

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
LOCKED_FIELDS = ("path", "chunk_idx", "heading_path")
LOCKED_SCORE_KEYS = ("bm25", "vector", "rrf", "final")


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


@pytest.fixture
def indexed_root(tmp_path: Path) -> Path:
    install_corpus(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    return tmp_path


def _slim(payload: dict) -> dict:
    """Project the JSON payload onto the locked fields only."""
    return {
        "query": payload["query"],
        "scope": payload["scope"],
        "results": [
            {
                **{k: r[k] for k in LOCKED_FIELDS},
                "scores": {k: round(r["scores"][k], 4) for k in LOCKED_SCORE_KEYS},
            }
            for r in payload["results"]
        ],
    }


def _check_or_write(name: str, slim: dict) -> None:
    p = SNAPSHOT_DIR / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        pytest.skip(f"snapshot {name} initialized; rerun to verify")
    expected = json.loads(p.read_text(encoding="utf-8"))
    assert slim == expected, f"snapshot mismatch: {name}\n  expected: {expected}\n  got: {slim}"


@pytest.mark.parametrize(
    "query,scope,snapshot",
    [
        ("OAuth 토큰 저장", "wiki", "search_oauth.json"),
        ("한국어 형태소", "wiki", "search_korean.json"),
        ("BM25 RRF", "raw", "search_rrf.json"),
    ],
)
def test_golden_search(indexed_root: Path, query: str, scope: str, snapshot: str):
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "search",
            query,
            "--scope",
            scope,
            "--no-rerank",
            "--json",
            "--root",
            str(indexed_root),
        ],
    )
    assert res.exit_code == 0, res.output
    _check_or_write(snapshot, _slim(json.loads(res.output)))
