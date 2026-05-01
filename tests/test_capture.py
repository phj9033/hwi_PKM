"""Tests for pkm.commands.capture (M2.5: create subcommand)."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_create_from_stdin(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "foo", "--title", "Foo"],
        input="body here\n",
    )
    assert res.exit_code == 0, res.output
    # Find the created file (date-prefixed slug)
    created = list((tmp_path / "data/raw/captures").glob("*-foo.md"))
    assert len(created) == 1
    fm, body = parse(created[0].read_text(encoding="utf-8"))
    assert fm["title"] == "Foo"
    assert fm["status"] == "draft"
    assert fm["source_type"] == "text"
    assert body == "body here\n"


def test_create_with_url_and_status(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "bar", "--title", "Bar",
         "--url", "https://x", "--status", "reviewed"],
        input="ignored",
    )
    assert res.exit_code == 0, res.output
    p = next((tmp_path / "data/raw/captures").glob("*-bar.md"))
    fm, _ = parse(p.read_text(encoding="utf-8"))
    assert fm["source_url"] == "https://x"
    assert fm["source_type"] == "url"
    assert fm["status"] == "reviewed"


def test_create_from_file(tmp_path: Path):
    _init(tmp_path)
    src = tmp_path / "in.md"
    src.write_text("from-file body", encoding="utf-8")
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "qux", "--title", "Qux", "--from-file", str(src)],
    )
    assert res.exit_code == 0
    p = next((tmp_path / "data/raw/captures").glob("*-qux.md"))
    _, body = parse(p.read_text(encoding="utf-8"))
    assert body == "from-file body"


def test_create_json_output(tmp_path: Path):
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "baz", "--title", "Baz", "--json"],
        input="b",
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["id"].endswith("-baz")
    assert "raw/captures" in payload["path"]


def test_create_appends_log_and_rebuilds_index(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "logme", "--title", "Logme"],
        input="b",
    )
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "capture.create" in log
    assert "logme" in log
    idx = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert "logme" in idx


def test_create_invalid_status_clean_error(tmp_path: Path):
    """Bad enum must surface as VALIDATION_ERROR, not a Python traceback."""
    _init(tmp_path)
    res = runner.invoke(
        app,
        ["capture", "create", "--root", str(tmp_path),
         "--slug", "x", "--title", "X", "--status", "weird"],
        input="b",
    )
    assert res.exit_code != 0
    assert "VALIDATION_ERROR" in res.output or "status" in res.output.lower()


def test_create_refuses_existing_slug(tmp_path: Path):
    _init(tmp_path)
    runner.invoke(app, ["capture", "create", "--root", str(tmp_path),
                        "--slug", "dup", "--title", "Dup"], input="x")
    res2 = runner.invoke(app, ["capture", "create", "--root", str(tmp_path),
                               "--slug", "dup", "--title", "Dup2"], input="y")
    assert res2.exit_code != 0
    assert "exists" in res2.output.lower() or "STATE_ERROR" in res2.output


def _create(tmp_path, slug, title="t", status="draft", lang="ko", url=None):
    args = ["capture", "create", "--root", str(tmp_path),
            "--slug", slug, "--title", title, "--status", status, "--lang", lang]
    if url:
        args += ["--url", url]
    return runner.invoke(app, args, input="body")


def test_list_returns_all(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a")
    _create(tmp_path, "b", status="reviewed")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    slugs = [it["slug"] for it in payload["items"]]
    assert any(s.endswith("-a") for s in slugs)
    assert any(s.endswith("-b") for s in slugs)


def test_list_filter_status(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a", status="draft")
    _create(tmp_path, "b", status="reviewed")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path),
                              "--status", "reviewed", "--json"])
    payload = json.loads(res.output)
    assert all(it["status"] == "reviewed" for it in payload["items"])
    assert any(it["slug"].endswith("-b") for it in payload["items"])


def test_list_filter_lang(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "a", lang="ko")
    _create(tmp_path, "b", lang="en")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path),
                              "--lang", "en", "--json"])
    payload = json.loads(res.output)
    assert all(it["lang"] == "en" for it in payload["items"])


def test_show_by_full_slug(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "uniq", title="Uniq")
    res = runner.invoke(app, ["capture", "list", "--root", str(tmp_path), "--json"])
    full = json.loads(res.output)["items"][0]["slug"]
    res2 = runner.invoke(app, ["capture", "show", full, "--root", str(tmp_path), "--json"])
    assert res2.exit_code == 0
    payload = json.loads(res2.output)
    assert payload["ok"] is True
    assert payload["frontmatter"]["title"] == "Uniq"


def test_show_by_partial_slug(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "uniq")
    res = runner.invoke(app, ["capture", "show", "uniq", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0


def test_show_not_found(tmp_path):
    _init(tmp_path)
    res = runner.invoke(app, ["capture", "show", "absent", "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_set_status_changes_frontmatter(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "promoteme", status="draft")
    res = runner.invoke(app, ["capture", "set-status", "promoteme", "reviewed",
                              "--root", str(tmp_path)])
    assert res.exit_code == 0
    res2 = runner.invoke(app, ["capture", "show", "promoteme",
                               "--root", str(tmp_path), "--json"])
    assert json.loads(res2.output)["frontmatter"]["status"] == "reviewed"


def test_set_status_invalid_enum(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "x")
    res = runner.invoke(app, ["capture", "set-status", "x", "weird",
                              "--root", str(tmp_path)])
    assert res.exit_code != 0


def test_rm_deletes_file_and_logs(tmp_path):
    _init(tmp_path)
    _create(tmp_path, "rmme")
    res = runner.invoke(app, ["capture", "rm", "rmme", "--root", str(tmp_path)])
    assert res.exit_code == 0
    assert not list((tmp_path / "data/raw/captures").glob("*-rmme.md"))
    log = (tmp_path / "data/log.md").read_text(encoding="utf-8")
    assert "capture.rm" in log
