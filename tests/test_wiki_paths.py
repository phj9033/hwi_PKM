"""Tests for pkm.store.wiki_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store import wiki_paths as wp


def _make_wiki(tmp_path: Path, bucket: str, slug: str) -> Path:
    p = tmp_path / "data" / "wiki" / bucket / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: t\n---\nbody\n", encoding="utf-8")
    return p


def test_wiki_dir(tmp_path: Path):
    assert wp.wiki_dir(tmp_path, "concepts") == tmp_path / "data" / "wiki" / "concepts"


def test_wiki_path(tmp_path: Path):
    assert wp.wiki_path(tmp_path, "notes", "foo") == tmp_path / "data" / "wiki" / "notes" / "foo.md"


def test_resolve_wiki_by_full_path(tmp_path: Path):
    p = _make_wiki(tmp_path, "concepts", "oauth")
    assert wp.resolve_wiki(tmp_path, "data/wiki/concepts/oauth.md") == p


def test_resolve_wiki_by_bucket_slash_slug(tmp_path: Path):
    p = _make_wiki(tmp_path, "entities", "anthropic")
    assert wp.resolve_wiki(tmp_path, "entities/anthropic") == p


def test_resolve_wiki_by_slug_unambiguous(tmp_path: Path):
    p = _make_wiki(tmp_path, "notes", "uniquely-named")
    assert wp.resolve_wiki(tmp_path, "uniquely-named") == p


def test_resolve_wiki_by_slug_ambiguous_raises(tmp_path: Path):
    _make_wiki(tmp_path, "concepts", "shared")
    _make_wiki(tmp_path, "notes", "shared")
    with pytest.raises(PKMValidationError):
        wp.resolve_wiki(tmp_path, "shared")


def test_resolve_wiki_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        wp.resolve_wiki(tmp_path, "does-not-exist")


def test_iter_all_wiki(tmp_path: Path):
    _make_wiki(tmp_path, "concepts", "a")
    _make_wiki(tmp_path, "concepts", "b")
    _make_wiki(tmp_path, "notes", "c")
    out = sorted(p.name for p in wp.iter_all_wiki(tmp_path))
    assert out == ["a.md", "b.md", "c.md"]
