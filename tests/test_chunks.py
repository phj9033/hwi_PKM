"""Tests for pkm.commands.chunks."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_new_creates_topic_with_readme(tmp_path):
    _init(tmp_path)
    res = runner.invoke(app, ["chunks", "new", "oauth-deep-dive",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    readme = tmp_path / "data/raw/chunks/oauth-deep-dive/README.md"
    assert readme.exists()
    fm, _ = parse(readme.read_text(encoding="utf-8"))
    assert fm["topic"] == "oauth-deep-dive"
    assert fm["status"] == "collecting"


def test_new_with_description(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x",
                        "--description", "deep dive on x",
                        "--root", str(tmp_path)])
    fm, _ = parse((tmp_path / "data/raw/chunks/x/README.md").read_text(encoding="utf-8"))
    assert fm["description"] == "deep dive on x"


def test_new_refuses_existing(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "dup", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "new", "dup", "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_add_copies_file_and_records_source(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "t", "--root", str(tmp_path)])
    src = tmp_path / "src.md"
    src.write_text("source content", encoding="utf-8")
    res = runner.invoke(app, ["chunks", "add", "t", str(src),
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    copied = tmp_path / "data/raw/chunks/t/src.md"
    assert copied.read_text(encoding="utf-8") == "source content"
    fm, _ = parse((tmp_path / "data/raw/chunks/t/README.md").read_text(encoding="utf-8"))
    assert "src.md" in fm["sources"]


def test_add_multiple_files(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "t", "--root", str(tmp_path)])
    a = tmp_path / "a.md"
    a.write_text("a")
    b = tmp_path / "b.md"
    b.write_text("b")
    res = runner.invoke(app, ["chunks", "add", "t", str(a), str(b),
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    fm, _ = parse((tmp_path / "data/raw/chunks/t/README.md").read_text(encoding="utf-8"))
    assert "a.md" in fm["sources"] and "b.md" in fm["sources"]


def test_add_refuses_missing_topic(tmp_path):
    _init(tmp_path)
    src = tmp_path / "x.md"
    src.write_text("x")
    res = runner.invoke(app, ["chunks", "add", "absent", str(src),
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_list_returns_topics(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "a", "--root", str(tmp_path)])
    runner.invoke(app, ["chunks", "new", "b", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "list", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    topics = [it["topic"] for it in payload["items"]]
    assert set(topics) >= {"a", "b"}


def test_show_returns_readme_and_files(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    src = tmp_path / "f.md"
    src.write_text("y")
    runner.invoke(app, ["chunks", "add", "x", str(src), "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "show", "x", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["topic"] == "x"
    assert any(p.endswith("f.md") for p in payload["files"])


def test_set_status_changes_state(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "set-status", "x", "ready",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    fm, _ = parse((tmp_path / "data/raw/chunks/x/README.md").read_text(encoding="utf-8"))
    assert fm["status"] == "ready"


def test_set_status_invalid_enum(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "x", "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "set-status", "x", "wat",
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_rm_removes_topic_tree(tmp_path):
    _init(tmp_path)
    runner.invoke(app, ["chunks", "new", "rm", "--root", str(tmp_path)])
    src = tmp_path / "f.md"
    src.write_text("y")
    runner.invoke(app, ["chunks", "add", "rm", str(src), "--root", str(tmp_path)])
    res = runner.invoke(app, ["chunks", "rm", "rm", "--root", str(tmp_path)])
    assert res.exit_code == 0
    assert not (tmp_path / "data/raw/chunks/rm").exists()
