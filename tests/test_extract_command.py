"""Tests for `pkm extract` CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_extract_pdf_to_stdout():
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.pdf")])
    assert result.exit_code == 0
    assert "Hello, PDF world." in result.stdout


def test_extract_html_to_stdout():
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.html")])
    assert result.exit_code == 0
    assert "샘플 제목" in result.stdout
    assert "**first**" in result.stdout


def test_extract_to_out_path(tmp_path: Path):
    out = tmp_path / "extracted.md"
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.pdf"), "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Hello, PDF world." in content


def test_extract_unknown_extension_errors(tmp_path: Path):
    weird = tmp_path / "doc.docx"
    weird.write_bytes(b"not actually docx")
    result = runner.invoke(app, ["extract", str(weird), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
