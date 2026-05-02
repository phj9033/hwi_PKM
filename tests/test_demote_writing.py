"""Tests for `pkm demote` with writing-origin pages (M5.12)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def _seed_wiki_dep(tmp_path: Path) -> None:
    """Create a wiki dep that derived_from can point to."""
    p = tmp_path / "data" / "wiki" / "concepts" / "dep.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\n"
        "title: Dep\n"
        "slug: dep\n"
        "bucket: concepts\n"
        "status: active\n"
        "lang: ko\n"
        "created_at: 2026-05-01T00:00:00+09:00\n"
        "updated_at: 2026-05-01T00:00:00+09:00\n"
        "derived_from: []\n"
        "tags: []\n"
        "---\n",
        encoding="utf-8",
    )


def _set_derived_from(writing_path: Path, dep_path: str) -> None:
    """Edit the writing file's derived_from to point at dep_path."""
    txt = writing_path.read_text(encoding="utf-8")
    txt = txt.replace("derived_from: []", f"derived_from:\n- {dep_path}")
    writing_path.write_text(txt, encoding="utf-8")


def _round_trip_promote_writing(tmp_path: Path) -> tuple[Path, Path]:
    """Helper: create a writing draft, promote to wiki, return (src, wiki) paths."""
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    src = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(src, "data/wiki/concepts/dep.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    wiki = tmp_path / "data" / "wiki" / "notes" / "draft1.md"
    return src, wiki


def test_demote_writing_happy(tmp_path: Path, monkeypatch) -> None:
    """Demote a writing-origin wiki page: wiki deleted, writing status → final."""
    monkeypatch.chdir(tmp_path)
    src, wiki = _round_trip_promote_writing(tmp_path)
    assert wiki.exists()
    assert "status: promoted" in src.read_text(encoding="utf-8")

    res = runner.invoke(app, ["demote", "notes/draft1", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.stdout
    out = json.loads(res.stdout)
    assert out["ok"] is True
    assert out["source_kind"] == "writing"
    assert out["writing_status_after"] == "final"
    assert not wiki.exists()
    assert "status: final" in src.read_text(encoding="utf-8")


def test_demote_writing_handles_keep_source_history(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: status=promoted now → demote restores final."""
    monkeypatch.chdir(tmp_path)
    _src, _wiki = _round_trip_promote_writing(tmp_path)
    res = runner.invoke(app, ["demote", "notes/draft1", "--root", str(tmp_path)])
    assert res.exit_code == 0


def test_demote_source_missing_errors(tmp_path: Path, monkeypatch) -> None:
    """Demote fails gracefully when writing source has vanished."""
    monkeypatch.chdir(tmp_path)
    src, _wiki = _round_trip_promote_writing(tmp_path)
    src.unlink()
    res = runner.invoke(app, ["demote", "notes/draft1", "--root", str(tmp_path)])
    assert res.exit_code != 0
    combined = (res.stdout or "") + (res.stderr or "")
    assert "vanished" in combined.lower() or "not found" in combined.lower()


def test_demote_writing_includes_git_commit(tmp_path: Path, monkeypatch) -> None:
    """JSON output includes git_commit SHA."""
    monkeypatch.chdir(tmp_path)
    _src, _wiki = _round_trip_promote_writing(tmp_path)
    res = runner.invoke(app, ["demote", "notes/draft1", "--root", str(tmp_path), "--json"])
    out = json.loads(res.stdout)
    assert "git_commit" in out and len(out["git_commit"]) >= 7
