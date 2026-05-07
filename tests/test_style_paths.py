"""Tests for pkm.store.style_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError
from pkm.store import style_paths as sp


def _make_sample(tmp_path: Path, style: str, sample: str) -> Path:
    p = tmp_path / "data" / "style" / style / f"{sample}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nslug: {sample}\ntitle: t\nlang: ko\n"
        f"created_at: 2026-05-07T10:00:00+09:00\n"
        f"updated_at: 2026-05-07T10:00:00+09:00\n"
        f"tags: []\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_style_dir(tmp_path: Path):
    assert sp.style_dir(tmp_path) == tmp_path / "data" / "style"


def test_style_root(tmp_path: Path):
    assert sp.style_root(tmp_path, "casual") == tmp_path / "data" / "style" / "casual"


def test_style_path(tmp_path: Path):
    assert (
        sp.style_path(tmp_path, "casual", "sample-1")
        == tmp_path / "data" / "style" / "casual" / "sample-1.md"
    )


def test_resolve_style_by_full_path(tmp_path: Path):
    p = _make_sample(tmp_path, "casual", "oauth")
    assert sp.resolve_style(tmp_path, "data/style/casual/oauth.md") == p


def test_resolve_style_by_style_and_sample(tmp_path: Path):
    p = _make_sample(tmp_path, "casual", "oauth")
    assert sp.resolve_style(tmp_path, "casual/oauth") == p


def test_resolve_style_bare_sample_rejected(tmp_path: Path):
    _make_sample(tmp_path, "casual", "oauth")
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "oauth")


def test_resolve_style_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "casual/nope")


def test_iter_styles(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "formal", "b")
    _make_sample(tmp_path, "casual", "c")  # second sample under casual
    names = sorted(p.name for p in sp.iter_styles(tmp_path))
    assert names == ["casual", "formal"]


def test_iter_style_samples(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "casual", "b")
    _make_sample(tmp_path, "formal", "c")
    names = sorted(p.name for p in sp.iter_style_samples(tmp_path, "casual"))
    assert names == ["a.md", "b.md"]


def test_iter_style_samples_unknown_style_yields_nothing(tmp_path: Path):
    assert list(sp.iter_style_samples(tmp_path, "nope")) == []


def test_iter_all_style_recurses(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "casual", "b")
    _make_sample(tmp_path, "formal", "c")
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in sp.iter_all_style(tmp_path))
    assert rels == [
        "data/style/casual/a.md",
        "data/style/casual/b.md",
        "data/style/formal/c.md",
    ]


def test_iter_all_style_skips_flat_files(tmp_path: Path):
    """Flat data/style/<name>.md files are not yielded by iter_all_style.

    Lint surfaces them as STYLE_FLAT_FILE; the path API quietly ignores them
    so downstream consumers (search/blog) only see properly-nested samples.
    """
    flat = tmp_path / "data" / "style" / "stray.md"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text("---\nslug: stray\n---\n", encoding="utf-8")
    _make_sample(tmp_path, "casual", "a")
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in sp.iter_all_style(tmp_path))
    assert rels == ["data/style/casual/a.md"]


def test_resolve_style_form1_preserves_relative_root(tmp_path, monkeypatch):
    """Same regression class as wiki_paths Form 1 — must not call .resolve()."""
    _make_sample(tmp_path, "casual", "oauth")
    monkeypatch.chdir(tmp_path)
    target = sp.resolve_style(Path("."), "data/style/casual/oauth.md")
    assert target.relative_to(Path(".")).as_posix() == "data/style/casual/oauth.md"


def test_resolve_style_multi_slash_rejected(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "foo/bar/baz")
