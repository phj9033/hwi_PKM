"""Tests for pkm/dashboard/pages/lists.py."""

from __future__ import annotations

import pytest

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.lists import build_list_page
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_empty(tmp_path):
    (tmp_path / "data").mkdir()
    from pkm.dashboard.scanner import scan as _scan

    return DashboardContext(root=tmp_path, registry=_scan(tmp_path))


def test_captures_list_renders_each_capture(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    p = build_list_page(out, ctx_seeded, "captures")
    html = p.read_text(encoding="utf-8")
    assert ">Alpha<" in html
    assert ">Beta<" in html
    assert "<table" in html


def test_wiki_list_links_to_doc_pages(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    p = build_list_page(out, ctx_seeded, "wiki")
    html = p.read_text(encoding="utf-8")
    assert 'href="doc/wiki/concepts/token-storage.html"' in html
    assert 'href="doc/wiki/notes/token-rotation.html"' in html


def test_chunks_list_topic_column(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    p = build_list_page(out, ctx_seeded, "chunks")
    assert "oauth" in p.read_text(encoding="utf-8")


def test_empty_category_renders_empty_marker(tmp_path, ctx_empty):
    out = tmp_path / "out"
    out.mkdir()
    p = build_list_page(out, ctx_empty, "writing")
    assert 'class="empty"' in p.read_text(encoding="utf-8")


def test_unknown_category_raises(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        build_list_page(out, ctx_seeded, "bogus")
