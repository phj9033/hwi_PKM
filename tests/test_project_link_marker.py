"""`pkm project link` writes a `.pkm-link` marker to cwd (best-effort)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_link_writes_marker_to_cwd(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    marker_path = tmp_code_repo / ".pkm-link"
    assert marker_path.is_file()
    assert marker_path.read_text(encoding="utf-8") == "my-app\n"


def test_link_json_payload_includes_marker_written(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["marker_written"] is True


def test_link_idempotent_re_writes_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    # Manually delete marker, then re-link
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    # ALREADY_LINKED is exit_code 0 per PKMAlreadyLinked.exit_code=0; marker should be recreated
    assert (tmp_code_repo / ".pkm-link").is_file()


def test_link_readonly_cwd_succeeds_with_warning(tmp_data_repo, tmp_code_repo, monkeypatch, capsys):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    os.chmod(tmp_code_repo, 0o500)
    try:
        result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    finally:
        os.chmod(tmp_code_repo, 0o700)
    assert result.exit_code == 0
    # Warning goes to stderr; JSON envelope goes to stdout. Parse stdout only.
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["marker_written"] is False
    assert "warning" in result.stderr.lower()
