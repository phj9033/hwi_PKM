"""pkm project link — register cwd's git repo as a project."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_link_creates_project_dir_and_index(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["project_id"] == "my-app"
    pdir = tmp_data_repo / "data" / "projects" / "my-app"
    assert (pdir / "index.md").is_file()
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        assert (pdir / cat).is_dir()


def test_link_idempotent_already_linked(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload.get("error", {}).get("code") == "ALREADY_LINKED"


def test_link_project_id_conflict(tmp_data_repo, tmp_code_repo_pair, monkeypatch):
    repo_a, repo_b = tmp_code_repo_pair
    _git_init(repo_a, remote="git@github.com:a/a.git")
    _git_init(repo_b, remote="git@github.com:b/b.git")
    monkeypatch.chdir(repo_a)
    runner.invoke(app, ["project", "link", "--id", "x", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    monkeypatch.chdir(repo_b)
    result = runner.invoke(app, ["project", "link", "--id", "x", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "PROJECT_ID_CONFLICT"


def test_link_invalid_project_id(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "Bad Slug!", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "INVALID_PROJECT_ID"


def test_link_not_a_git_repo(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)  # no git init
    result = runner.invoke(app, ["project", "link", "--id", "x", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "NOT_A_GIT_REPO"
