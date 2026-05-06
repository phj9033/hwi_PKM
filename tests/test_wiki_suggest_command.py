"""Tests for `pkm wiki suggest <slug>`."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect

runner = CliRunner()
_DIM = 1024


def _unit(angle_rad: float, second_axis: int = 1) -> np.ndarray:
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle_rad)
    v[second_axis] = math.sin(angle_rad)
    return v


def _scaffold(root: Path):
    (root / ".pkm").mkdir(parents=True, exist_ok=True)
    (root / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    return connect(root)


def _seed_two_close(root: Path):
    conn = _scaffold(root)
    (root / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "concepts" / "b.md").write_text(
        "---\nslug: b\ntitle: B\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    conn.execute(
        "INSERT INTO documents(id, path, bucket, title, lang, status, "
        "frontmatter_json, content_hash, indexed_at) VALUES "
        "(1, 'data/wiki/concepts/a.md', 'wiki', 'A', 'ko', 'active', '{}', 'h', '2026')"
    )
    conn.execute(
        "INSERT INTO documents(id, path, bucket, title, lang, status, "
        "frontmatter_json, content_hash, indexed_at) VALUES "
        "(2, 'data/wiki/concepts/b.md', 'wiki', 'B', 'ko', 'active', '{}', 'h', '2026')"
    )
    a = _unit(0.0)
    b = _unit(math.acos(0.92))
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (1, ?)", (a.tobytes(),))
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (2, ?)", (b.tobytes(),))
    conn.commit()
    conn.close()


def test_suggest_text_output(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(app, ["wiki", "suggest", "a", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "data/wiki/concepts/b.md" in res.output
    assert "0.9" in res.output  # similarity rounded to 0.92


def test_suggest_json_output(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app, ["wiki", "suggest", "a", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["slug"] == "a"
    assert len(payload["suggestions"]) == 1
    s = payload["suggestions"][0]
    assert s["path"] == "data/wiki/concepts/b.md"
    assert s["slug"] == "b"
    assert s["similarity"] >= 0.9


def test_suggest_unknown_slug(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app, ["wiki", "suggest", "nope", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_suggest_no_index(tmp_path: Path):
    """No .pkm/index.db at all → INDEX_MISSING."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    res = runner.invoke(
        app, ["wiki", "suggest", "a", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "INDEX_MISSING"


def test_suggest_threshold_override(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app,
        ["wiki", "suggest", "a", "--root", str(tmp_path), "--threshold", "0.99", "--json"],
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["suggestions"] == []
