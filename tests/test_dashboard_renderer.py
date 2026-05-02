"""Tests for pkm/dashboard/renderer.py."""

from __future__ import annotations

from pkm.dashboard.renderer import make_snippet, render_markdown
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


def test_render_resolves_wikilink_to_doc_page(tmp_path):
    seed(tmp_path)
    reg = scan(tmp_path)
    html = render_markdown("See [[token-rotation]] please.", reg, depth=3)
    # depth=3 (doc/wiki/<bucket>/<slug>.html) → ../../../doc/wiki/notes/token-rotation.html
    assert 'class="wikilink"' in html
    assert "../../../doc/wiki/notes/token-rotation.html" in html
    # Title (Token Rotation) used as the link text per renderer convention.
    assert ">Token Rotation</a>" in html


def test_render_marks_broken_wikilink(tmp_path):
    seed(tmp_path)
    reg = scan(tmp_path)
    html = render_markdown("See [[does-not-exist]].", reg, depth=0)
    assert 'class="wikilink-broken"' in html
    assert ">does-not-exist</span>" in html


def test_render_passes_through_fenced_code_and_tables(tmp_path):
    seed(tmp_path)
    reg = scan(tmp_path)
    md = "```python\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    html = render_markdown(md, reg, depth=0)
    assert "<pre>" in html and "<code" in html
    assert "<table>" in html


def test_make_snippet_strips_markdown():
    body = "# Heading\n\nSome **bold** text and a [link](https://x).\n\nMore..."
    s = make_snippet(body, max_chars=40)
    assert "#" not in s
    assert "**" not in s
    assert "[link]" not in s
    assert len(s) <= 40
    assert "Some bold text" in s


def test_make_snippet_short_body_returned_verbatim():
    s = make_snippet("hello world", max_chars=200)
    assert s == "hello world"
