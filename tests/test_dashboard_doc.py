"""Tests for pkm/dashboard/pages/doc.py — wiki + writing doc pages."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.doc import build_doc_page
from pkm.dashboard.scanner import Neighbor, scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    """Seed corpus + reindex DB so link graph is populated."""
    seed(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_no_db(tmp_path):
    """Seed corpus but skip reindex — DB missing → empty link graphs."""
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_with_semantic(ctx_seeded):
    """Inject synthetic semantic neighbors for token-storage."""
    reg = ctx_seeded.registry
    storage = reg.by_slug["token-storage"]
    rotation = reg.by_slug["token-rotation"]
    reg.semantic[storage.rel_path] = [
        Neighbor(rel_path=rotation.rel_path, title=rotation.title, score=0.91),
    ]
    return ctx_seeded


@pytest.fixture
def ctx_with_secret_doc(tmp_path):
    """Seed corpus plus a wiki doc with a secret-shaped frontmatter key."""
    seed(tmp_path)
    (tmp_path / "data" / "wiki" / "concepts" / "creds.md").write_text(
        "---\n"
        "title: Creds\n"
        "slug: creds\n"
        "status: active\n"
        "lang: en\n"
        "api_token: supersecret\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


def test_doc_page_renders_body_and_sidebar(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["token-storage"]
    p = build_doc_page(tmp_path / "out", ctx_seeded, doc)
    html = p.read_text(encoding="utf-8")
    assert ">Token Storage<" in html
    assert "<aside" in html
    # Outgoing wikilink resolved in body, depth=3 → ../../../ prefix.
    assert "doc/wiki/notes/token-rotation.html" in html


def test_doc_page_backlinks(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["token-rotation"]
    p = build_doc_page(tmp_path / "out", ctx_seeded, doc)
    html = p.read_text(encoding="utf-8")
    assert 'class="backlinks"' in html
    # token-storage links into rotation
    assert "token-storage" in html


def test_doc_page_semantic_neighbors_when_present(tmp_path, ctx_with_semantic):
    doc = ctx_with_semantic.registry.by_slug["token-storage"]
    p = build_doc_page(tmp_path / "out", ctx_with_semantic, doc)
    html = p.read_text(encoding="utf-8")
    assert 'class="semantic-neighbors"' in html
    assert "Token Rotation" in html


def test_doc_page_semantic_empty_when_index_missing(tmp_path, ctx_no_db):
    doc = ctx_no_db.registry.by_slug["token-storage"]
    p = build_doc_page(tmp_path / "out", ctx_no_db, doc)
    html = p.read_text(encoding="utf-8")
    assert 'class="empty"' in html
    assert "pkm reindex db" in html


def test_doc_page_provenance_writing(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["team-oauth-guideline"]
    p = build_doc_page(tmp_path / "out", ctx_seeded, doc)
    html = p.read_text(encoding="utf-8")
    assert "derived_from" in html.lower() or 'class="provenance"' in html
    assert "token-storage" in html


def test_doc_page_secret_masking_in_frontmatter(tmp_path, ctx_with_secret_doc):
    """Wiki doc with frontmatter key matching mask pattern → value rendered as ***."""
    doc = ctx_with_secret_doc.registry.by_slug["creds"]
    p = build_doc_page(tmp_path / "out", ctx_with_secret_doc, doc)
    html = p.read_text(encoding="utf-8")
    assert "***" in html
    assert "supersecret" not in html


def test_doc_page_writes_to_url_path(tmp_path, ctx_seeded):
    """File is written at out/<doc.url_path>; parent dirs are created."""
    doc = ctx_seeded.registry.by_slug["token-storage"]
    out = tmp_path / "out"
    p = build_doc_page(out, ctx_seeded, doc)
    assert p == out / doc.url_path
    assert p.exists()
