"""Tests for `pkm wiki edit --replace`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Seed one wiki page directly (this is what promote will normally do)
    target = tmp_path / "data" / "wiki" / "concepts" / "oauth.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        "title: OAuth\n"
        "slug: oauth\n"
        "bucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\n"
        "lang: ko\n"
        "tags: []\n"
        "---\n"
        "Original body.\n",
        encoding="utf-8",
    )
    # Track it in git so promote/demote/edit chains see a clean tree
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wiki"], cwd=tmp_path, check=True)
    return tmp_path


REPLACEMENT = (
    "---\n"
    "title: OAuth\n"
    "slug: oauth\n"
    "bucket: concepts\n"
    "created_at: 2026-05-01T10:00:00+09:00\n"
    "updated_at: 2026-05-02T11:00:00+09:00\n"
    "status: active\n"
    "lang: ko\n"
    "tags: [auth]\n"
    "---\n"
    "Updated body. See [[csrf]] for related.\n"
)


def test_wiki_edit_replace_writes_and_returns_sha(initialized_repo: Path):
    # Seed the wikilink target so [[csrf]] resolves
    csrf = initialized_repo / "data" / "wiki" / "concepts" / "csrf.md"
    csrf.write_text(
        "---\ntitle: CSRF\nslug: csrf\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []\n---\nstub\n",
        encoding="utf-8",
    )
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=initialized_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add csrf"], cwd=initialized_repo, check=True)

    result = runner.invoke(
        app,
        ["wiki", "edit", "concepts/oauth", "--replace", "--root", str(initialized_repo), "--json"],
        input=REPLACEMENT,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["path"] == "data/wiki/concepts/oauth.md"
    assert payload["git_commit"] is not None
    body = (initialized_repo / "data" / "wiki" / "concepts" / "oauth.md").read_text(
        encoding="utf-8"
    )
    assert "Updated body." in body
    assert "[[csrf]]" in body


def test_wiki_edit_replace_rejects_missing_required_frontmatter(initialized_repo: Path):
    bad = "---\ntitle: x\n---\nbody\n"
    result = runner.invoke(
        app,
        ["wiki", "edit", "concepts/oauth", "--replace", "--root", str(initialized_repo), "--json"],
        input=bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_wiki_edit_replace_rejects_broken_wikilink(initialized_repo: Path):
    body_with_bad = REPLACEMENT.replace("[[csrf]]", "[[does-not-exist]]")
    result = runner.invoke(
        app,
        ["wiki", "edit", "concepts/oauth", "--replace", "--root", str(initialized_repo), "--json"],
        input=body_with_bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert (
        "BROKEN_WIKILINK" in payload["error"]["code"]
        or "does-not-exist" in payload["error"]["message"]
    )


def test_wiki_edit_replace_unknown_ref(initialized_repo: Path):
    result = runner.invoke(
        app,
        ["wiki", "edit", "missing-slug", "--replace", "--root", str(initialized_repo), "--json"],
        input=REPLACEMENT,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_wiki_edit_replace_disallows_changing_slug(initialized_repo: Path):
    # The path's slug is "oauth" but the new frontmatter says "renamed"
    bad = REPLACEMENT.replace("slug: oauth", "slug: renamed")
    result = runner.invoke(
        app,
        ["wiki", "edit", "concepts/oauth", "--replace", "--root", str(initialized_repo), "--json"],
        input=bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
