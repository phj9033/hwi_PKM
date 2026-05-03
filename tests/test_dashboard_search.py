"""Tests for pkm/dashboard/pages/search.py — search.html + search-index.json."""

from __future__ import annotations

import json

import pytest

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.search import build_search
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_with_long_body(tmp_path):
    seed(tmp_path)
    # Append a writing doc with a body well above 200 chars.
    long_body = "x" * 500
    (tmp_path / "data" / "writing" / "long-doc.md").write_text(
        "---\ntitle: Long Doc\nslug: long-doc\nstatus: draft\nlang: en\n---\n" + long_body + "\n",
        encoding="utf-8",
    )
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


def test_search_writes_html_and_json(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    html_path, json_path = build_search(out, ctx_seeded)
    assert html_path.exists() and json_path.exists()


def test_search_index_includes_all_categories(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    _, json_path = build_search(out, ctx_seeded)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    paths = {d["path"] for d in data}
    assert "raw/captures/alpha.md" in paths
    assert "wiki/concepts/token-storage.md" in paths
    assert "writing/team-oauth-guideline.md" in paths


def test_search_index_url_empty_for_captures(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    _, json_path = build_search(out, ctx_seeded)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    capture = next(d for d in data if d["path"].startswith("raw/captures/"))
    assert capture["url"] == ""


def test_search_index_snippet_truncated(tmp_path, ctx_with_long_body):
    out = tmp_path / "out"
    out.mkdir()
    _, json_path = build_search(out, ctx_with_long_body)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert all(len(d["snippet"]) <= 200 for d in data)


def test_search_html_loads_search_js(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    html_path, _ = build_search(out, ctx_seeded)
    text = html_path.read_text(encoding="utf-8")
    assert "search-index.json" in text
    assert "search.js" in text
