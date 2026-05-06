"""`pkm write new --from-search` should surface find_suggestions_for results
for any wiki entries currently in derived_from (M11)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect

runner = CliRunner()
_DIM = 1024


@pytest.fixture(autouse=True)
def _stub_embedder(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _unit(angle: float, axis: int = 1):
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle)
    v[axis] = math.sin(angle)
    return v


def _seed_two_close_wiki(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    for slug in ("oauth-tokens", "session-cookies"):
        (tmp_path / "data" / "wiki" / "concepts" / f"{slug}.md").write_text(
            f"---\nslug: {slug}\ntitle: {slug}\nbucket: concepts\nstatus: active\n"
            "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
            "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
            encoding="utf-8",
        )
    conn = connect(tmp_path)
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(1,'data/wiki/concepts/oauth-tokens.md','wiki','OAuth tokens','ko',"
        "'active','{}','h','2026')"
    )
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(2,'data/wiki/concepts/session-cookies.md','wiki','Session cookies','ko',"
        "'active','{}','h','2026')"
    )
    a = _unit(0.0)
    b = _unit(math.acos(0.92))
    conn.execute("INSERT INTO docs_vec(doc_id,embedding) VALUES (1, ?)", (a.tobytes(),))
    conn.execute("INSERT INTO docs_vec(doc_id,embedding) VALUES (2, ?)", (b.tobytes(),))
    conn.commit()
    conn.close()


def test_write_new_includes_related_suggestions(tmp_path: Path):
    """A writing seeded from a wiki page (via --from-search) lists semantically
    close wiki neighbours as related_suggestions in JSON output.

    We simulate this by passing the wiki path directly into the `--from-search`
    seed string; the implementation looks at any wiki paths it can resolve from
    the seed and surfaces their suggestions. The exact resolution heuristic is
    documented in the implementation.
    """
    _seed_two_close_wiki(tmp_path)
    res = runner.invoke(
        app,
        [
            "write", "new",
            "--slug", "draft1",
            "--from-search", "oauth-tokens",  # implementation matches this to a wiki slug
            "--purpose", "summary",
            "--root", str(tmp_path),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    related = payload.get("related_suggestions", [])
    paths = [r["path"] for r in related]
    assert "data/wiki/concepts/session-cookies.md" in paths


def test_write_new_no_related_when_no_index(tmp_path: Path):
    """No .pkm/index.db → related_suggestions is an empty list (silent)."""
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / ".pkm" / "index.db").unlink(missing_ok=True)
    res = runner.invoke(
        app,
        [
            "write", "new",
            "--slug", "draft2",
            "--from-search", "anything",
            "--purpose", "summary",
            "--root", str(tmp_path),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload.get("related_suggestions", []) == []
