"""Tests for the 6 Error-severity lint rules."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _write(p: Path, fm_text: str, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def _commit(repo: Path) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed test data"], cwd=repo, check=True)


def _codes(findings) -> list[str]:
    return sorted(f.code for f in findings)


def test_missing_field_capture(tmp_path: Path):
    repo = _init(tmp_path)
    _write(
        repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
        "title: X\nslug: 2026-05-01-x\nstatus: draft\nlang: ko",  # missing created_at + source_type
        "body",
    )
    _commit(repo)
    findings = list(collect_findings(repo))
    assert "MISSING_FIELD" in _codes(findings)


def test_invalid_value_status(tmp_path: Path):
    repo = _init(tmp_path)
    _write(
        repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
        "title: X\nslug: 2026-05-01-x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
        "status: bogus\nsource_type: text\nlang: ko",
        "body",
    )
    _commit(repo)
    assert "INVALID_VALUE" in _codes(collect_findings(repo))


def test_duplicate_slug_in_same_bucket(tmp_path: Path):
    repo = _init(tmp_path)
    base_fm = (
        "title: A\nslug: shared\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []"
    )
    _write(repo / "data" / "wiki" / "concepts" / "shared.md", base_fm, "x")
    # Two files with same slug — rename file but slug field stays "shared"
    _write(
        repo / "data" / "wiki" / "concepts" / "alt.md", base_fm.replace("title: A", "title: B"), "y"
    )
    _commit(repo)
    assert "DUPLICATE_SLUG" in _codes(collect_findings(repo))


def test_broken_wikilink(tmp_path: Path):
    repo = _init(tmp_path)
    _write(
        repo / "data" / "wiki" / "concepts" / "page.md",
        "title: P\nslug: page\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: active\nlang: ko\ntags: []",
        "See [[nonexistent]] for context.",
    )
    _commit(repo)
    assert "BROKEN_WIKILINK" in _codes(collect_findings(repo))


def test_broken_derived_from(tmp_path: Path):
    repo = _init(tmp_path)
    _write(
        repo / "data" / "wiki" / "concepts" / "page.md",
        "title: P\nslug: page\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: active\nlang: ko\ntags: []\n"
        "derived_from: [data/wiki/concepts/missing.md]",
        "body",
    )
    _commit(repo)
    assert "BROKEN_DERIVED_FROM" in _codes(collect_findings(repo))


def test_orphan_promoted_source(tmp_path: Path):
    repo = _init(tmp_path)
    # Capture status=reviewed (NOT archived), wiki has promoted_from pointing at it
    _write(
        repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
        "title: X\nslug: 2026-05-01-x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
        "status: reviewed\nsource_type: text\nlang: ko",
        "body",
    )
    _write(
        repo / "data" / "wiki" / "concepts" / "x.md",
        "title: X\nslug: x\nbucket: concepts\n"
        "created_at: 2026-05-02T10:00:00+09:00\n"
        "updated_at: 2026-05-02T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []\n"
        "promoted_from: data/raw/captures/2026-05-01-x.md",
        "body",
    )
    _commit(repo)
    codes = _codes(collect_findings(repo))
    assert "ORPHAN_PROMOTED_SOURCE" in codes
