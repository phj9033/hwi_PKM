"""Tests for the M11 grounding hard-gate on `pkm promote` (writing → wiki)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _bootstrap(repo: Path) -> None:
    runner.invoke(app, ["init", "--root", str(repo)])


def _capture(repo: Path, slug: str) -> Path:
    p = repo / "data" / "raw" / "captures" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntitle: {slug}\nslug: {slug}\nsource_type: text\nstatus: reviewed\n"
        f"lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    return p


def _writing(
    repo: Path, slug: str, *, derived_from, body, purpose="report", exempt=False
):
    p = repo / "data" / "writing" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not derived_from:
        df_block = "derived_from: []"
    else:
        df_block = "derived_from:\n  - " + "\n  - ".join(derived_from)
    extra = "\ngrounding_exempt: true" if exempt else ""
    p.write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: final\npurpose: {purpose}\n"
        f"{df_block}\nlang: ko\ntags: []\n"
        "created_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00{extra}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return p


def test_promote_passes_when_grounding_clean(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "clean",
        derived_from=["data/raw/captures/src.md"],
        body="Body cites [data/raw/captures/src.md] inline.",
    )
    res = runner.invoke(
        app, ["promote", "clean", "--to", "concepts", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True


def test_promote_fails_citation_not_derived(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")  # exists but not in derived_from
    _writing(
        tmp_path,
        "cite-not-derived",
        derived_from=[],
        body="Body cites [data/raw/captures/src.md] which isn't in derived_from.",
    )
    res = runner.invoke(
        app,
        [
            "promote", "cite-not-derived", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "CITATION_NOT_DERIVED"


def test_promote_fails_derived_not_cited(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "derived-not-cited",
        derived_from=["data/raw/captures/src.md"],
        body="Body that never cites src.",
    )
    res = runner.invoke(
        app,
        [
            "promote", "derived-not-cited", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "DERIVED_NOT_CITED"


def test_promote_fails_ungrounded_long_body(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "ungrounded",
        derived_from=[],
        body=("가" * 600),
        purpose="report",
    )
    res = runner.invoke(
        app,
        ["promote", "ungrounded", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "UNGROUNDED_WRITING"


def test_promote_passes_with_exempt_flag(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "exempt",
        derived_from=[],
        body=("가" * 600),
        purpose="report",
        exempt=True,
    )
    res = runner.invoke(
        app,
        ["promote", "exempt", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 0, res.output


def test_promote_passes_for_essay_purpose(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "essay-piece",
        derived_from=[],
        body=("가" * 600),
        purpose="essay",
    )
    res = runner.invoke(
        app,
        ["promote", "essay-piece", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 0, res.output


def test_essay_still_enforces_r1(tmp_path: Path):
    """essay exempts R3 only; R1 still applies."""
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "essay-with-stray-cite",
        derived_from=[],
        body="Body cites [data/raw/captures/src.md] but it's not in derived_from.",
        purpose="essay",
    )
    res = runner.invoke(
        app,
        [
            "promote", "essay-with-stray-cite", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "CITATION_NOT_DERIVED"
