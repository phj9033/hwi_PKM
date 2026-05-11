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


def test_write_new_file(tmp_path: Path):
    assert marker.write(tmp_path, "my-app") is True
    assert (tmp_path / ".pkm-link").read_text(encoding="utf-8") == "my-app\n"


def test_write_overwrites_existing(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("old-id\n", encoding="utf-8")
    assert marker.write(tmp_path, "new-id") is True
    assert (tmp_path / ".pkm-link").read_text(encoding="utf-8") == "new-id\n"


def test_write_readonly_dir_returns_false(tmp_path: Path):
    import os
    sub = tmp_path / "ro"
    sub.mkdir()
    os.chmod(sub, 0o500)  # r-x — no write
    try:
        assert marker.write(sub, "x") is False
    finally:
        os.chmod(sub, 0o700)  # restore so tmp_path cleanup works


def test_delete_existing(tmp_path: Path):
    (tmp_path / ".pkm-link").write_text("x\n", encoding="utf-8")
    assert marker.delete(tmp_path) is True
    assert not (tmp_path / ".pkm-link").exists()


def test_delete_missing_returns_true(tmp_path: Path):
    # Idempotent: nothing to delete is success.
    assert marker.delete(tmp_path) is True


def test_delete_directory_returns_false(tmp_path: Path):
    (tmp_path / ".pkm-link").mkdir()
    assert marker.delete(tmp_path) is False
