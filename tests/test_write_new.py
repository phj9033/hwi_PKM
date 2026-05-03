import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def test_write_new_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "foo", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["ok"] is True
    p = tmp_path / "data" / "writing" / "foo.md"
    assert p.exists()


def test_write_new_records_search_seed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(
        app, ["write", "new", "--slug", "foo", "--from-search", "OAuth 토큰", "--json"]
    )
    out = json.loads(res.stdout)
    assert out["frontmatter"]["search_seed"] == "OAuth 토큰"


def test_write_new_from_chunks_fills_derived_from(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["chunks", "new", "oauth"])
    chunks = tmp_path / "data" / "raw" / "chunks" / "oauth"
    (chunks / "src1.md").write_text("a", encoding="utf-8")
    (chunks / "src2.md").write_text("b", encoding="utf-8")
    res = runner.invoke(
        app, ["write", "new", "--slug", "draft1", "--from-chunks", "oauth", "--json"]
    )
    out = json.loads(res.stdout)
    derived = out["frontmatter"]["derived_from"]
    assert any("src1.md" in p for p in derived)
    assert any("src2.md" in p for p in derived)


def test_write_new_body_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "foo"])
    p = tmp_path / "data" / "writing" / "foo.md"
    txt = p.read_text(encoding="utf-8")
    body_start = txt.rfind("---") + len("---")
    assert txt[body_start:].strip() == ""


def test_write_new_rejects_dual_seed_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(
        app, ["write", "new", "--slug", "x", "--from-search", "q", "--from-chunks", "t"]
    )
    assert res.exit_code == 2


def test_write_new_invalid_purpose(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "x", "--purpose", "rant"])
    assert res.exit_code == 2


def test_write_new_includes_git_commit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "foo", "--json"])
    out = json.loads(res.stdout)
    assert "git_commit" in out and len(out["git_commit"]) >= 7
