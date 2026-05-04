"""Tests for pkm.store.style_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError
from pkm.store import style_paths as sp


def _make_style(tmp_path: Path, slug: str) -> Path:
    p = tmp_path / "data" / "style" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nslug: {slug}\ntitle: t\nlang: ko\n"
        f"created_at: 2026-05-04T10:00:00+09:00\n"
        f"updated_at: 2026-05-04T10:00:00+09:00\n"
        f"tags: []\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_style_dir(tmp_path: Path):
    assert sp.style_dir(tmp_path) == tmp_path / "data" / "style"


def test_style_path(tmp_path: Path):
    assert sp.style_path(tmp_path, "foo") == tmp_path / "data" / "style" / "foo.md"


def test_resolve_style_by_full_path(tmp_path: Path):
    p = _make_style(tmp_path, "oauth")
    assert sp.resolve_style(tmp_path, "data/style/oauth.md") == p


def test_resolve_style_by_slug(tmp_path: Path):
    p = _make_style(tmp_path, "oauth-token-storage")
    assert sp.resolve_style(tmp_path, "oauth-token-storage") == p


def test_resolve_style_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "nope")


def test_iter_all_style(tmp_path: Path):
    _make_style(tmp_path, "a")
    _make_style(tmp_path, "b")
    _make_style(tmp_path, "c")
    assert sorted(p.name for p in sp.iter_all_style(tmp_path)) == ["a.md", "b.md", "c.md"]


def test_resolve_style_form1_preserves_relative_root(tmp_path, monkeypatch):
    # Same regression class as wiki_paths Form 1 — Form 1 must not call .resolve()
    _make_style(tmp_path, "oauth")
    monkeypatch.chdir(tmp_path)
    target = sp.resolve_style(Path("."), "data/style/oauth.md")
    assert target.relative_to(Path(".")).as_posix() == "data/style/oauth.md"
