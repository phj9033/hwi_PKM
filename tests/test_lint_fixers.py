"""Tests for lint auto-fixers."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.fixers import fix_missing_field, fix_orphan_promoted_source
from pkm.lint.rules import LintFinding

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def test_fix_missing_field_created_at(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\ntitle: X\nslug: 2026-05-01-x\n"
        "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
        encoding="utf-8",
    )
    finding = LintFinding(
        "MISSING_FIELD",
        "error",
        "data/raw/captures/2026-05-01-x.md",
        "missing",
        field="created_at",
        fixable=True,
    )
    assert fix_missing_field(repo, finding) is True
    assert "created_at:" in p.read_text(encoding="utf-8")


def test_fix_missing_field_slug_from_file_stem(tmp_path: Path):
    """Slug fixer uses the file stem — preserves date prefix for captures."""
    repo = _init(tmp_path)
    # Capture's file stem already includes the date prefix
    p = repo / "data" / "raw" / "captures" / "2026-05-01-some-title.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\ntitle: Some Title\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
        encoding="utf-8",
    )
    finding = LintFinding(
        "MISSING_FIELD",
        "error",
        "data/raw/captures/2026-05-01-some-title.md",
        "missing",
        field="slug",
        fixable=True,
    )
    assert fix_missing_field(repo, finding) is True
    # Date-prefixed slug, derived from file stem
    assert "slug: 2026-05-01-some-title" in p.read_text(encoding="utf-8")


def test_fix_missing_field_slug_for_wiki_uses_stem(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "wiki" / "concepts" / "oauth.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\ntitle: OAuth\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []\n---\nbody\n",
        encoding="utf-8",
    )
    finding = LintFinding(
        "MISSING_FIELD",
        "error",
        "data/wiki/concepts/oauth.md",
        "missing",
        field="slug",
        fixable=True,
    )
    assert fix_missing_field(repo, finding) is True
    assert "slug: oauth" in p.read_text(encoding="utf-8")


def test_fix_missing_field_unfixable_returns_false(tmp_path: Path):
    repo = _init(tmp_path)
    finding = LintFinding(
        "MISSING_FIELD", "error", "data/wiki/concepts/x.md", "missing", field="title", fixable=False
    )
    assert fix_missing_field(repo, finding) is False


def test_fix_orphan_promoted_source(tmp_path: Path):
    repo = _init(tmp_path)
    src = repo / "data" / "raw" / "captures" / "2026-05-01-x.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(
        "---\ntitle: X\nslug: 2026-05-01-x\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "status: reviewed\nsource_type: text\nlang: ko\n---\nbody\n",
        encoding="utf-8",
    )
    wiki = repo / "data" / "wiki" / "concepts" / "x.md"
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(
        "---\ntitle: X\nslug: x\nbucket: concepts\n"
        "created_at: 2026-05-02T10:00:00+09:00\n"
        "updated_at: 2026-05-02T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []\n"
        "promoted_from: data/raw/captures/2026-05-01-x.md\n---\nbody\n",
        encoding="utf-8",
    )
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    finding = LintFinding(
        "ORPHAN_PROMOTED_SOURCE", "error", "data/wiki/concepts/x.md", "...", fixable=True
    )
    assert fix_orphan_promoted_source(repo, finding) is True
    assert "status: archived" in src.read_text(encoding="utf-8")
