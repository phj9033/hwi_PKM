"""5-step cwd → project-id resolver."""

from __future__ import annotations

from pathlib import Path
import pytest
from pkm.session.registry import resolve_project_id, ProjectIndex, ProjectRecord


def _idx(*records: ProjectRecord) -> ProjectIndex:
    return ProjectIndex(records=list(records))


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("PKM_PROJECT", "manual-id")
    idx = _idx()
    assert resolve_project_id(tmp_path, project_index=idx) == "manual-id"


def test_local_override_beats_git(monkeypatch, tmp_path):
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    overrides = {str(tmp_path): "override-id"}
    idx = _idx(ProjectRecord(id="git-id", git_remotes=["github.com:user/repo"], local_paths=[]))
    result = resolve_project_id(tmp_path, project_index=idx, local_overrides=overrides, _git_remote="github.com:user/repo")
    assert result == "override-id"


def test_git_remote_match(tmp_path):
    idx = _idx(ProjectRecord(id="git-id", git_remotes=["github.com:user/repo"], local_paths=[]))
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote="github.com:user/repo")
    assert result == "git-id"


def test_local_path_fallback(tmp_path):
    idx = _idx(ProjectRecord(id="path-id", git_remotes=[], local_paths=[str(tmp_path)]))
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote=None)
    assert result == "path-id"


def test_returns_none_when_nothing_matches(tmp_path):
    idx = _idx()
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote=None)
    assert result is None


def test_project_index_loads_from_data_repo(tmp_path):
    """ProjectIndex.load() reads frontmatter from data/projects/*/index.md"""
    pdir = tmp_path / "data" / "projects" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:test/demo\ncreated_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n",
        encoding="utf-8",
    )
    idx = ProjectIndex.load(tmp_path)
    assert len(idx.records) == 1
    assert idx.records[0].id == "demo"
    assert idx.records[0].git_remotes == ["github.com:test/demo"]
