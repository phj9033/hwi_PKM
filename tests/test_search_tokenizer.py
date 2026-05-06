"""Tests for pkm.search.tokenizer adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.search import tokenizer as tk
from pkm.store.index_db import connect


def test_get_tokenizer_trigram_always_available():
    spec = tk.get_tokenizer("trigram")
    assert spec.name == "trigram"
    assert spec.available is True
    assert "trigram" in spec.fts5_create_args


def test_detect_active_returns_trigram_for_v1_schema(tmp_path: Path):
    conn = connect(tmp_path)
    assert tk.detect_active(conn) == "trigram"
    conn.close()


def test_tokenize_for_indexing_trigram_passes_through():
    spec = tk.get_tokenizer("trigram")
    out = tk.tokenize_for_indexing("hello world", lang="en", tokenizer=spec)
    assert out == "hello world"


def test_tokenize_for_indexing_kiwi_lang_en_passes_through():
    """Even with kiwi tokenizer, English text is passed through unchanged."""
    spec = tk.get_tokenizer("kiwi")
    if not spec.available:
        pytest.skip("kiwipiepy not installed (extra '[korean]' missing)")
    out = tk.tokenize_for_indexing("hello world", lang="en", tokenizer=spec)
    assert out == "hello world"


def test_tokenize_for_indexing_kiwi_lang_ko_segments_morphemes():
    spec = tk.get_tokenizer("kiwi")
    if not spec.available:
        pytest.skip("kiwipiepy not installed")
    out = tk.tokenize_for_indexing("환경설정의 인증 토큰", lang="ko", tokenizer=spec)
    assert " " in out
    assert len(out) >= len("환경설정의 인증 토큰")


def test_get_tokenizer_auto_returns_kiwi_when_available():
    spec = tk.get_tokenizer("auto")
    if tk.get_tokenizer("kiwi").available:
        assert spec.name == "kiwi"
    else:
        assert spec.name == "trigram"


def test_get_tokenizer_unknown_name_falls_back_to_trigram():
    spec = tk.get_tokenizer("nonexistent-tokenizer")
    assert spec.name == "trigram"
