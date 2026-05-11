"""`pkm doctor` surfaces marker diagnostics for the cwd."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def _doctor_marker_item(json_output: str) -> dict | None:
    payload = json.loads(json_output)
    for item in payload["items"]:
        if item["name"] == "marker":
            return item
    return None


def test_doctor_marker_ok_when_linked_and_marker_matches(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "ok"


def test_doctor_marker_missing(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "missing"
    assert "MARKER_MISSING" in (item["detail"] or "")


def test_doctor_marker_mismatch(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").write_text("wrong-id\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_MISMATCH" in (item["detail"] or "")


def test_doctor_marker_orphan(tmp_data_repo, tmp_code_repo, monkeypatch):
    # No link; just a stray marker
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").write_text("stale\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_ORPHAN" in (item["detail"] or "")


def test_doctor_marker_invalid(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").mkdir()
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item["status"] == "missing"
    assert "MARKER_INVALID" in (item["detail"] or "")


def test_doctor_marker_ok_when_not_linked_and_no_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["doctor", "--json", "--root", str(tmp_data_repo)])
    item = _doctor_marker_item(result.output)
    assert item is not None
    assert item["status"] == "ok"


def test_doctor_fix_creates_missing_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    result = runner.invoke(app, ["doctor", "--fix", "--json", "--root", str(tmp_data_repo)])
    assert result.exit_code == 0
    assert (tmp_code_repo / ".pkm-link").is_file()
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "my-app"


def test_doctor_fix_overwrites_mismatched_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").write_text("wrong\n", encoding="utf-8")
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    assert (tmp_code_repo / ".pkm-link").read_text(encoding="utf-8").strip() == "my-app"


def test_doctor_fix_removes_orphan_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").write_text("stale\n", encoding="utf-8")
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_doctor_fix_removes_invalid_marker(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    (tmp_code_repo / ".pkm-link").mkdir()
    runner.invoke(app, ["doctor", "--fix", "--root", str(tmp_data_repo)])
    # Invalid removed; nothing recreated since cwd is NOT_LINKED
    assert not (tmp_code_repo / ".pkm-link").exists()


def test_doctor_without_fix_does_not_mutate(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--data-repo", str(tmp_data_repo)])
    (tmp_code_repo / ".pkm-link").unlink()
    runner.invoke(app, ["doctor", "--root", str(tmp_data_repo)])
    # No --fix → marker remains absent
    assert not (tmp_code_repo / ".pkm-link").exists()
