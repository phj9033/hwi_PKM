"""Unit tests for pkm.marker — cwd-local .pkm-link file IO."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm import marker


def test_read_missing_returns_none(tmp_path: Path):
    assert marker.read(tmp_path) is None


def test_read_single_line(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("my-app\n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_strips_whitespace(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("  my-app  \n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_first_non_empty_line(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("\n\nmy-app\nextra-line\n", encoding="utf-8")
    assert marker.read(tmp_path) == "my-app"


def test_read_empty_file_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("", encoding="utf-8")
    assert marker.read(tmp_path) is None


def test_read_whitespace_only_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("   \n\n  \n", encoding="utf-8")
    assert marker.read(tmp_path) is None


def test_read_directory_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").mkdir()
    assert marker.read(tmp_path) is None


def test_read_non_utf8_returns_none(tmp_path: Path):
    (tmp_path / ".pkm-link").write_bytes(b"\xff\xfe not utf8")
    assert marker.read(tmp_path) is None
