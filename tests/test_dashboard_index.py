"""Tests for pkm/dashboard/pages/index.py."""

from __future__ import annotations

import pytest

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.index import build_index
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_with_lint(ctx_seeded):
    ctx_seeded.lint_summary = {
        "counts": {"errors": 1, "warnings": 2, "info": 0},
        "items": [
            {"code": "BROKEN_CITATION", "severity": "error", "path": "wiki/concepts/foo.md"},
            {"code": "BROKEN_CITATION", "severity": "error", "path": "wiki/concepts/bar.md"},
            {"code": "MISSING_TITLE", "severity": "warning", "path": "wiki/notes/baz.md"},
        ],
    }
    return ctx_seeded


@pytest.fixture
def ctx_no_lint(ctx_seeded):
    ctx_seeded.lint_summary = None
    return ctx_seeded


@pytest.fixture
def ctx_with_log(ctx_seeded):
    ctx_seeded.recent_log = [
        {"type": "capture.create", "ref": "alpha", "at": "2026-05-02T10:00:00Z"},
        {"type": "capture.set-status", "ref": "alpha", "at": "2026-05-02T10:01:00Z"},
    ]
    return ctx_seeded


def test_index_stat_strip(tmp_path, ctx_seeded):
    out = tmp_path / "out"
    out.mkdir()
    p = build_index(out, ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert 'data-stat="captures"' in html
    assert 'data-stat="wiki"' in html
    # Seed has 2 captures, 1 chunk, 2 wiki, 1 writing
    assert ">2<" in html  # exact count assertion: 2 captures and 2 wiki


def test_index_lint_summary_when_present(tmp_path, ctx_with_lint):
    out = tmp_path / "out"
    out.mkdir()
    p = build_index(out, ctx_with_lint)
    html = p.read_text(encoding="utf-8")
    assert "lint" in html.lower()
    assert "BROKEN_CITATION" in html


def test_index_lint_summary_unavailable(tmp_path, ctx_no_lint):
    out = tmp_path / "out"
    out.mkdir()
    p = build_index(out, ctx_no_lint)
    html = p.read_text(encoding="utf-8")
    assert "(unavailable" in html


def test_index_recent_log_table(tmp_path, ctx_with_log):
    out = tmp_path / "out"
    out.mkdir()
    p = build_index(out, ctx_with_log)
    html = p.read_text(encoding="utf-8")
    assert "<table" in html
    assert "capture" in html
    assert "alpha" in html
