"""Lint warnings for the M11 grounding rules — surface violations BEFORE promote.

The 4 rules mirror promote-time hard gates so users see them in `pkm lint`
output without invoking promote.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _seed_writing(repo: Path, slug: str, *, derived_from, body, purpose="report"):
    (repo / "data" / "writing").mkdir(parents=True, exist_ok=True)
    if not derived_from:
        df_block = "derived_from: []"
    else:
        df_block = "derived_from:\n  - " + "\n  - ".join(derived_from)
    (repo / "data" / "writing" / f"{slug}.md").write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: draft\npurpose: {purpose}\n"
        f"{df_block}\nlang: ko\ntags: []\n"
        "created_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_lint_warns_citation_not_derived(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw" / "captures" / "src.md").write_text(
        "---\ntitle: src\nslug: src\nsource_type: text\nstatus: reviewed\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    _seed_writing(
        tmp_path, "stray",
        derived_from=[],
        body="Per [data/raw/captures/src.md].",
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    codes = [item["code"] for item in payload["warnings"]]
    assert "CITATION_NOT_DERIVED" in codes


def test_lint_warns_ungrounded(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    _seed_writing(
        tmp_path, "ungrounded",
        derived_from=[],
        body=("가" * 600),
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    codes = [item["code"] for item in payload["warnings"]]
    assert "UNGROUNDED_WRITING" in codes


def test_lint_silent_on_clean_writing(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw" / "captures" / "src.md").write_text(
        "---\ntitle: src\nslug: src\nsource_type: text\nstatus: reviewed\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    _seed_writing(
        tmp_path, "clean",
        derived_from=["data/raw/captures/src.md"],
        body="Per [data/raw/captures/src.md].",
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    codes = {item["code"] for item in payload["warnings"]}
    assert "CITATION_NOT_DERIVED" not in codes
    assert "UNGROUNDED_WRITING" not in codes
    assert "DERIVED_NOT_CITED" not in codes
