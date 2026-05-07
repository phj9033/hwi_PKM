"""pkm project knowledge add — write a project knowledge markdown."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _link(tmp_data_repo, tmp_code_repo, monkeypatch, pid="demo"):
    subprocess.run(["git", "init"], cwd=tmp_code_repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@github.com:t/t.git"],
                   cwd=tmp_code_repo, check=True, capture_output=True)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", pid, "--no-commit", "--json",
                        "--data-repo", str(tmp_data_repo)])


def test_knowledge_add_creates_file(tmp_data_repo, tmp_code_repo, monkeypatch):
    _link(tmp_data_repo, tmp_code_repo, monkeypatch)
    result = runner.invoke(app, [
        "project", "knowledge", "add",
        "--project", "demo",
        "--category", "decisions",
        "--slug", "oauth-cookie",
        "--title", "OAuth in cookie",
        "--source-type", "ai_session",
        "--no-commit",
        "--json",
        "--data-repo", str(tmp_data_repo),
    ], input="body line 1\nbody line 2\n")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    p = tmp_data_repo / "data" / "projects" / "demo" / "decisions" / f"{payload['slug']}.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "category: decisions" in text
    assert "body line 1" in text


def test_knowledge_add_slug_auto_dated(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Slug without YYYY-MM-DD- prefix gets one prepended."""
    _link(tmp_data_repo, tmp_code_repo, monkeypatch)
    result = runner.invoke(app, [
        "project", "knowledge", "add",
        "--project", "demo", "--category", "decisions",
        "--slug", "raw-slug", "--title", "T",
        "--no-commit", "--json",
        "--data-repo", str(tmp_data_repo),
    ], input="body\n")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert re.match(r"^\d{4}-\d{2}-\d{2}-raw-slug$", payload["slug"])


def test_knowledge_add_invalid_category(tmp_data_repo, tmp_code_repo, monkeypatch):
    _link(tmp_data_repo, tmp_code_repo, monkeypatch)
    result = runner.invoke(app, [
        "project", "knowledge", "add",
        "--project", "demo",
        "--category", "nonsense",
        "--slug", "x", "--title", "T",
        "--no-commit", "--json",
        "--data-repo", str(tmp_data_repo),
    ], input="body\n")
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "INVALID_CATEGORY"
