"""Tests for pkm.extract.html."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.extract import html as htmlmod

FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_html_to_markdown_h1():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    assert "샘플 제목" in out
    assert ("# " in out) or ("=" * 3 in out)


def test_html_to_markdown_strong_to_asterisks():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    assert "**first**" in out


def test_html_to_markdown_list_items():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    assert "한 항목" in out
    assert "another item" in out


def test_html_to_markdown_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        htmlmod.html_to_markdown(tmp_path / "missing.html")
