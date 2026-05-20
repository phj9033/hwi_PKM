from __future__ import annotations

import subprocess

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.commands.capture import _parse_tags
from pkm.errors import PKMValidationError


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)
    # initial commit so post_mutation works
    (path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=path, check=True, capture_output=True)


def test_parse_tags_json():
    assert _parse_tags('["a","b","c"]') == ["a", "b", "c"]


def test_parse_tags_comma():
    assert _parse_tags("a, b ,c") == ["a", "b", "c"]


def test_parse_tags_empty():
    assert _parse_tags("") == []
    assert _parse_tags(None) is None


def test_parse_tags_bad_json_raises():
    with pytest.raises(PKMValidationError):
        _parse_tags('["unterminated')


def test_capture_create_with_tags_and_summary(tmp_path):
    _init_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "capture", "create",
            "--slug", "test-cap",
            "--title", "Test",
            "--tags", '["llm","caching"]',
            "--summary", "Three-line summary here.",
            "--root", str(tmp_path),
            "--json",
        ],
        input="body content\n",
    )
    assert result.exit_code == 0, result.output
    # Verify the file got both fields in frontmatter
    captures = list((tmp_path / "data" / "raw" / "captures").glob("*.md"))
    assert len(captures) == 1
    content = captures[0].read_text(encoding="utf-8")
    assert "tags:" in content
    assert "llm" in content and "caching" in content
    assert "Three-line summary here." in content


def test_capture_create_with_comma_tags(tmp_path):
    _init_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "capture", "create",
            "--slug", "comma-test",
            "--title", "Comma",
            "--tags", "go, rust, python",
            "--root", str(tmp_path),
            "--json",
        ],
        input="body\n",
    )
    assert result.exit_code == 0, result.output
    content = list((tmp_path / "data" / "raw" / "captures").glob("*.md"))[0].read_text("utf-8")
    assert "go" in content and "rust" in content and "python" in content
