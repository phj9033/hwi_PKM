"""Tests for lint behavior on data/style/ (M8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _seed_style(tmp_path: Path, slug: str, body: str = "body\n", **fm_overrides) -> Path:
    p = tmp_path / "data" / "style" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "slug": slug,
        "title": "t",
        "lang": "ko",
        "created_at": "2026-05-04T10:00:00+09:00",
        "updated_at": "2026-05-04T10:00:00+09:00",
        "tags": [],
    }
    fm.update(fm_overrides)
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm.items() if v is not None)
    p.write_text(f"---\n{fm_lines}\n---\n{body}", encoding="utf-8")
    return p


def test_lint_clean_style_sample(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x")
    findings = list(collect_findings(tmp_path))
    relevant = [f for f in findings if f.path.startswith("data/style/")]
    assert relevant == []


def test_lint_style_missing_required_field(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / "data" / "style" / "x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nslug: x\ntitle: t\n# missing lang/created_at/updated_at\n---\nbody\n",
        encoding="utf-8",
    )
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/x.md"]
    codes = {f.code for f in findings}
    assert "MISSING_FIELD" in codes


def test_lint_style_invalid_lang(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x", lang="fr")
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/x.md"]
    codes = {f.code for f in findings}
    assert "INVALID_VALUE" in codes


def test_lint_style_skips_wikilink_check(tmp_path: Path):
    """Style samples reference external content — wiki slug match must not be enforced."""
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x", body="See [[nonexistent-wiki-slug]] for details.\n")
    findings = [
        f for f in collect_findings(tmp_path)
        if f.path == "data/style/x.md" and f.code == "BROKEN_WIKILINK"
    ]
    assert findings == []
