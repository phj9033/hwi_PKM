"""Tests for pkm.store.refs."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store.refs import resolve_capture, resolve_chunk_topic


def _mkcapture(root: Path, slug: str) -> Path:
    p = root / "data/raw/captures" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nslug: {slug}\n---\nbody", encoding="utf-8")
    return p


def test_resolve_capture_exact_slug(tmp_path: Path):
    p = _mkcapture(tmp_path, "2026-05-01-foo")
    assert resolve_capture(tmp_path, "2026-05-01-foo") == p


def test_resolve_capture_substring(tmp_path: Path):
    p = _mkcapture(tmp_path, "2026-05-01-foo-bar")
    assert resolve_capture(tmp_path, "foo-bar") == p


def test_resolve_capture_ambiguous_raises(tmp_path: Path):
    _mkcapture(tmp_path, "2026-05-01-x")
    _mkcapture(tmp_path, "2026-05-02-x")
    with pytest.raises(PKMValidationError, match="ambiguous"):
        resolve_capture(tmp_path, "x")


def test_resolve_capture_not_found(tmp_path: Path):
    (tmp_path / "data/raw/captures").mkdir(parents=True)
    with pytest.raises(PKMNotFoundError):
        resolve_capture(tmp_path, "nope")


def test_resolve_chunk_topic(tmp_path: Path):
    topic_dir = tmp_path / "data/raw/chunks/oauth"
    topic_dir.mkdir(parents=True)
    (topic_dir / "README.md").write_text("---\ntopic: oauth\n---\n", encoding="utf-8")
    assert resolve_chunk_topic(tmp_path, "oauth") == topic_dir


def test_resolve_chunk_topic_not_found(tmp_path: Path):
    (tmp_path / "data/raw/chunks").mkdir(parents=True)
    with pytest.raises(PKMNotFoundError):
        resolve_chunk_topic(tmp_path, "absent")
