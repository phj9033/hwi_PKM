"""pkm related --scope behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _add_other_project(repo: Path):
    """Append a second project 'other' with identical body text to demo's OAuth file.

    The stub embedder is SHA-256 hash-based — semantically meaningless — so we
    use the EXACT SAME body text as the demo project's OAuth decision so that
    mean-pooled doc vectors are identical (distance ≈ 0) and the 'other' doc
    always appears as a top semantic neighbor of the demo doc.
    """
    pdir = repo / "data" / "projects" / "other"
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        (pdir / cat).mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: other\ngit_remotes:\n  - github.com:test/other\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n"
        "---\n\n# other\n", encoding="utf-8",
    )
    # Body text must be IDENTICAL to demo's oauth-cookie so that the stub
    # embedder produces the same vector and the doc appears in neighbor results.
    (pdir / "decisions" / "2026-05-07-other-oauth.md").write_text(
        "---\ntitle: OAuth in cookie\nslug: 2026-05-07-other-oauth\n"
        "created_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\n"
        "source_type: ai_session\nlang: en\nproject: other\ncategory: decisions\n"
        "tags: []\n---\n\n"
        "OAuth refresh tokens stored in httpOnly cookies.\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(repo)])


def test_related_scope_same_project_excludes_other(tmp_indexed_data_repo, monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    _add_other_project(tmp_indexed_data_repo)
    result = runner.invoke(app, [
        "related",
        "data/projects/demo/decisions/2026-05-07-oauth-cookie.md",
        "--mode", "semantic", "--scope", "same-project",
        "--json", "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    neighbors = payload["related"].get("semantic_neighbors", [])
    paths = [n["path"] for n in neighbors]
    assert all(p.startswith("data/projects/demo/") for p in paths), paths


def test_related_scope_all_includes_other_project(tmp_indexed_data_repo, monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    _add_other_project(tmp_indexed_data_repo)
    result = runner.invoke(app, [
        "related",
        "data/projects/demo/decisions/2026-05-07-oauth-cookie.md",
        "--mode", "semantic", "--scope", "all",
        "--json", "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    neighbors = payload["related"].get("semantic_neighbors", [])
    paths = [n["path"] for n in neighbors]
    # Should reach the 'other' project's similar OAuth file
    assert any(p.startswith("data/projects/other/") for p in paths), paths


def test_related_scope_wiki_only(tmp_indexed_data_repo, monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    _add_other_project(tmp_indexed_data_repo)
    result = runner.invoke(app, [
        "related",
        "data/projects/demo/decisions/2026-05-07-oauth-cookie.md",
        "--mode", "semantic", "--scope", "wiki",
        "--json", "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    neighbors = payload["related"].get("semantic_neighbors", [])
    paths = [n["path"] for n in neighbors]
    assert all(p.startswith("data/wiki/") for p in paths), paths


def test_related_scope_auto_for_wiki_source_unfiltered(tmp_indexed_data_repo, monkeypatch):
    """Auto on a wiki source = unfiltered (current behavior)."""
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    _add_other_project(tmp_indexed_data_repo)
    result = runner.invoke(app, [
        "related",
        "data/wiki/concepts/oauth.md",
        "--mode", "semantic", "--scope", "auto",
        "--json", "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # Should see project-side neighbors when source is wiki (no constraint applied)
    neighbors = payload["related"].get("semantic_neighbors", [])
    assert neighbors  # at least something
