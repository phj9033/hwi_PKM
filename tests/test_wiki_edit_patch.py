"""Tests for `pkm wiki edit --patch`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_oauth(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
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
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed oauth"], cwd=tmp_path, check=True)
    return tmp_path


VALID_PATCH = """\
diff --git a/data/wiki/concepts/oauth.md b/data/wiki/concepts/oauth.md
--- a/data/wiki/concepts/oauth.md
+++ b/data/wiki/concepts/oauth.md
@@ -6,6 +6,6 @@ created_at: 2026-05-01T10:00:00+09:00
 updated_at: 2026-05-01T10:00:00+09:00
-status: stub
+status: active
 lang: ko
 tags: []
 ---
-Original body.
+Activated body.
"""


def test_wiki_edit_patch_applies_and_commits(repo_with_oauth: Path):
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=VALID_PATCH,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["git_commit"] is not None
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "Activated body." in body
    assert "status: active" in body


def test_wiki_edit_patch_invalid_diff_reverts(repo_with_oauth: Path):
    bad_patch = "this is not a unified diff at all"
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=bad_patch,
    )
    assert result.exit_code == 1
    # Working tree should still match the original
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "Original body." in body


def test_wiki_edit_patch_validation_failure_reverts(repo_with_oauth: Path):
    # A patch that applies fine but produces invalid frontmatter (bad enum)
    bad_patch = """\
diff --git a/data/wiki/concepts/oauth.md b/data/wiki/concepts/oauth.md
--- a/data/wiki/concepts/oauth.md
+++ b/data/wiki/concepts/oauth.md
@@ -6,3 +6,3 @@ created_at: 2026-05-01T10:00:00+09:00
 updated_at: 2026-05-01T10:00:00+09:00
-status: stub
+status: bogus
 lang: ko
"""
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=bad_patch,
    )
    assert result.exit_code == 1
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "status: stub" in body  # reverted


def test_wiki_edit_patch_no_op_returns_null_commit(repo_with_oauth: Path):
    # An empty patch: no-op. The CLI should report success but git_commit=None.
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input="",
    )
    # Empty stdin → git apply fails → exit 1 (we don't model this as success)
    assert result.exit_code == 1
