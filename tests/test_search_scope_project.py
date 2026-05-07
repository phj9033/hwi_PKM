"""New search scopes: project, project:<id>, projects, all (extended)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_search_scope_project_filters_to_current(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    result = runner.invoke(app, [
        "search", "oauth", "--scope", "project", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = [r["path"] for r in payload["results"]]
    assert paths, f"no hits at all: {payload}"
    assert all(p.startswith("data/projects/demo/") for p in paths), paths


def test_search_scope_project_specific_id(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, [
        "search", "oauth", "--scope", "project:demo", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = [r["path"] for r in payload["results"]]
    assert paths
    assert all(p.startswith("data/projects/demo/") for p in paths), paths


def test_search_scope_projects_includes_all_projects(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, [
        "search", "oauth", "--scope", "projects", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = [r["path"] for r in payload["results"]]
    assert any(p.startswith("data/projects/") for p in paths), paths


def test_search_default_scope_when_unlinked(tmp_indexed_data_repo, tmp_unlinked_cwd, monkeypatch):
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    monkeypatch.chdir(tmp_unlinked_cwd)
    result = runner.invoke(app, [
        "search", "oauth", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = [r["path"] for r in payload["results"]]
    # Default for unlinked cwd should reach wiki at minimum
    assert any(p.startswith("data/wiki/") for p in paths), paths


def test_search_unknown_scope_string(tmp_indexed_data_repo, monkeypatch):
    """Unknown scope token should error cleanly, not crash."""
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    result = runner.invoke(app, [
        "search", "oauth", "--scope", "bogus-scope", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code != 0
