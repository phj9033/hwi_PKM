"""Tests for pkm.extract.pdf."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.extract import pdf as pdfmod

FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_pdf_to_markdown_extracts_text():
    out = pdfmod.pdf_to_markdown(FIXTURES / "sample.pdf")
    assert "Hello, PDF world." in out
    assert "한국어" in out


def test_pdf_to_markdown_returns_unicode():
    out = pdfmod.pdf_to_markdown(FIXTURES / "sample.pdf")
    assert isinstance(out, str)
    # No mojibake — the original characters survive
    assert "한국어 본문" in out


def test_pdf_to_markdown_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        pdfmod.pdf_to_markdown(tmp_path / "does-not-exist.pdf")
