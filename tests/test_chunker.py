"""Tests for pkm.store.chunker."""
from __future__ import annotations

import pytest

from pkm.store.chunker import Chunk, split_markdown


def test_empty_returns_no_chunks():
    assert split_markdown("") == []


def test_single_paragraph_one_chunk():
    chunks = split_markdown("Hello world.")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].chunk_idx == 0
    assert chunks[0].heading_path == []


def test_frontmatter_stripped():
    text = "---\ntitle: x\n---\nBody only."
    chunks = split_markdown(text)
    assert len(chunks) == 1
    assert "title" not in chunks[0].text
    assert chunks[0].text.strip() == "Body only."


def test_heading_path_recorded():
    text = "# H1\n\n## H2\n\nbody under h2"
    chunks = split_markdown(text)
    assert chunks[-1].heading_path == ["H1", "H2"]


def test_multiple_headings_yield_multiple_chunks():
    text = "# A\n\nalpha body.\n\n# B\n\nbeta body."
    chunks = split_markdown(text)
    assert len(chunks) >= 2
    texts = [c.text for c in chunks]
    assert any("alpha" in t for t in texts)
    assert any("beta" in t for t in texts)


def test_long_section_split_on_token_cap():
    # 600 short words → must split into ≥2 chunks given target_tokens=500
    body = " ".join(f"word{i}" for i in range(600))
    text = f"# Big\n\n{body}"
    chunks = split_markdown(text, target_tokens=500, overlap=0.15)
    assert len(chunks) >= 2


def test_korean_sentence_boundary():
    # Korean ending 다. should be treated as sentence boundary
    text = "# 제목\n\n첫 문장이다. 두 번째 문장이다. 세 번째 문장이다."
    chunks = split_markdown(text)
    # No exception, chunks contain Korean text intact
    assert any("문장" in c.text for c in chunks)


def test_chunk_idx_monotonic():
    text = "# A\n\nx\n\n# B\n\ny\n\n# C\n\nz"
    chunks = split_markdown(text)
    assert [c.chunk_idx for c in chunks] == list(range(len(chunks)))


def test_token_count_present():
    chunks = split_markdown("# X\n\nhello world here")
    assert chunks[0].token_count >= 1
