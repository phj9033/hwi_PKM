"""`pkm project rm` deletes .pkm-link only when cwd matches AND marker content matches."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_rm_deletes_marker_when_cwd_matches(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").is_file()
    result = runner.invoke(app, ["project", "rm", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_rm_preserves_marker_when_content_mismatches(tmp_data_repo, tmp_code_repo, monkeypatch):
    """If marker exists but contains a different project_id, leave it alone."""
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    # Tamper marker to point at a different id
    (tmp_code_repo / ".pkm-link").write_text("other-id\n", encoding="utf-8")
    runner.invoke(app, ["project", "rm", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").is_file()
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "other-id"


def test_rm_preserves_marker_when_cwd_not_matched(tmp_data_repo, tmp_code_repo_pair, monkeypatch):
    """rm from a different cwd than where link happened → marker untouched."""
    repo_a, repo_b = tmp_code_repo_pair
    _git_init(repo_a, remote="git@github.com:a/a.git")
    _git_init(repo_b, remote="git@github.com:b/b.git")
    monkeypatch.chdir(repo_a)
    runner.invoke(app, ["project", "link", "--id", "proj-a", "--no-commit", "--data-repo", str(tmp_data_repo)])
    assert (repo_a / ".pkm-link").is_file()
    # rm from repo_b's cwd
    monkeypatch.chdir(repo_b)
    runner.invoke(app, ["project", "rm", "proj-a", "--no-commit", "--data-repo", str(tmp_data_repo)])
    # repo_a's marker is stale orphan — left for `doctor` to clean up later
    assert (repo_a / ".pkm-link").is_file()
