"""Tests for pkm.store.files."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path

import pytest

from pkm.store.files import atomic_write, date_prefix_slug, slugify


def test_slugify_simple():
    assert slugify("Hello World") == "hello-world"


def test_slugify_korean_preserved():
    assert slugify("한글 제목 테스트") == "한글-제목-테스트"


def test_slugify_korean_stripped_when_disabled():
    s = slugify("한글 Hello World", allow_korean=False)
    assert "한" not in s
    assert "hello-world" in s


def test_slugify_punctuation_removed():
    assert slugify("Why? Auth/OAuth!") == "why-auth-oauth"


def test_slugify_collapses_multiple_hyphens():
    assert slugify("a--b---c") == "a-b-c"


def test_slugify_strips_edge_hyphens():
    assert slugify("---a-b---") == "a-b"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("???")


def test_slugify_lowercases():
    assert slugify("OAuth") == "oauth"


def test_date_prefix_slug():
    assert date_prefix_slug("Hello", on=date(2026, 5, 1)) == "2026-05-01-hello"


def test_date_prefix_slug_korean():
    assert date_prefix_slug("한글 제목", on=date(2026, 5, 1)) == "2026-05-01-한글-제목"


def test_atomic_write_creates_parent_dir(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    atomic_write(target, "content")
    assert target.read_text(encoding="utf-8") == "content"


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "file.txt"
    atomic_write(target, "first")
    atomic_write(target, "second")
    assert target.read_text(encoding="utf-8") == "second"


def test_atomic_write_no_partial_file_on_failure(tmp_path: Path, monkeypatch):
    """If os.replace fails mid-way, no .tmp file remains and target is untouched."""
    target = tmp_path / "file.txt"

    def boom(*a, **k):
        raise OSError("simulated failure")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated"):
        atomic_write(target, "content")

    assert not target.exists()
    leftovers = list(tmp_path.glob(".file.txt.*.tmp"))
    assert not leftovers


def test_atomic_write_korean_content(tmp_path: Path):
    target = tmp_path / "ko.md"
    atomic_write(target, "한글 본문 내용\n")
    assert target.read_text(encoding="utf-8") == "한글 본문 내용\n"
