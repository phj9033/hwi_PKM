import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "list", "--json"])
    out = json.loads(res.stdout)
    assert out["items"] == []


def test_list_returns_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    runner.invoke(app, ["write", "new", "--slug", "b"])
    res = runner.invoke(app, ["write", "list", "--json"])
    out = json.loads(res.stdout)
    slugs = [it["slug"] for it in out["items"]]
    assert set(slugs) == {"a", "b"}


def test_list_filters_by_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    runner.invoke(app, ["write", "new", "--slug", "b"])
    runner.invoke(app, ["write", "set-status", "a", "final"])
    res = runner.invoke(app, ["write", "list", "--status", "final", "--json"])
    out = json.loads(res.stdout)
    assert [it["slug"] for it in out["items"]] == ["a"]


def test_set_status_transitions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    res = runner.invoke(app, ["write", "set-status", "a", "final", "--json"])
    out = json.loads(res.stdout)
    assert out["status"] == "final"
    assert "git_commit" in out


def test_set_status_rejects_promoted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    res = runner.invoke(app, ["write", "set-status", "a", "promoted"])
    assert res.exit_code == 2
