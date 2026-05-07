"""Dashboard graph: include_projects + project_filter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.dashboard.context import _read_graph_payload, _read_graph_config

runner = CliRunner()


@pytest.fixture
def tmp_indexed_data_repo_with_projects(tmp_path, monkeypatch):
    """Data repo with 2 projects + 1 wiki page, all indexed."""
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    repo = tmp_path / "datarepo"
    repo.mkdir()
    for sub in ("data/raw/captures", "data/wiki/concepts", "data/writing", "data/projects"):
        (repo / sub).mkdir(parents=True)
    (repo / ".pkm").mkdir()
    (repo / ".pkm" / "config.toml").write_text("# scaffolded\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True, capture_output=True)

    runner.invoke(app, ["migrate", "--apply", "--root", str(repo)])

    # 1 wiki page
    (repo / "data" / "wiki" / "concepts" / "oauth.md").write_text(
        "---\nslug: oauth\ntitle: OAuth\nbucket: concepts\nstatus: active\n"
        "lang: en\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "updated_at: 2026-05-07T00:00:00+09:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )

    # 2 projects: demo + other, each with 1 decision file
    for pid in ("demo", "other"):
        pdir = repo / "data" / "projects" / pid
        for cat in ("decisions", "pitfalls", "snippets", "qna", "notes"):
            (pdir / cat).mkdir(parents=True)
        (pdir / "index.md").write_text(
            f"---\nproject: {pid}\ngit_remotes:\n  - github.com:t/{pid}\n"
            "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n"
            f"---\n\n# {pid}\n",
            encoding="utf-8",
        )
        (pdir / "decisions" / f"2026-05-07-{pid}-x.md").write_text(
            f"---\ntitle: {pid} decision\nslug: 2026-05-07-{pid}-x\n"
            "created_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\n"
            f"source_type: ai_session\nlang: en\nproject: {pid}\ncategory: decisions\n"
            "tags: []\n---\n\nbody\n",
            encoding="utf-8",
        )

    runner.invoke(app, ["reindex", "db", "--full", "--root", str(repo)])
    return repo


def _write_config(repo: Path, **kwargs):
    """Append graph config to config.toml."""
    cfg = "\n[dashboard.graph]\n"
    for k, v in kwargs.items():
        if isinstance(v, bool):
            cfg += f"{k} = {'true' if v else 'false'}\n"
        elif isinstance(v, list):
            cfg += f"{k} = {json.dumps(v)}\n"
        else:
            cfg += f"{k} = {v}\n"
    (repo / ".pkm" / "config.toml").write_text(cfg, encoding="utf-8")


def test_include_projects_default_true(tmp_indexed_data_repo_with_projects):
    payload = _read_graph_payload(tmp_indexed_data_repo_with_projects)
    assert payload is not None
    project_nodes = [n for n in payload["nodes"] if n["id"].startswith("data/projects/")]
    assert project_nodes, [n["id"] for n in payload["nodes"]]


def test_include_projects_false_excludes(tmp_indexed_data_repo_with_projects):
    _write_config(tmp_indexed_data_repo_with_projects, include_projects=False)
    payload = _read_graph_payload(tmp_indexed_data_repo_with_projects)
    project_nodes = [n for n in payload["nodes"] if n["id"].startswith("data/projects/")]
    assert not project_nodes


def test_project_filter_restricts(tmp_indexed_data_repo_with_projects):
    _write_config(tmp_indexed_data_repo_with_projects, include_projects=True, project_filter=["demo"])
    payload = _read_graph_payload(tmp_indexed_data_repo_with_projects)
    project_nodes = [n for n in payload["nodes"] if n["id"].startswith("data/projects/")]
    assert project_nodes
    for n in project_nodes:
        assert n["id"].startswith("data/projects/demo/"), n["id"]


def test_max_nodes_cap_with_projects(tmp_indexed_data_repo_with_projects):
    _write_config(tmp_indexed_data_repo_with_projects, max_nodes=2)
    payload = _read_graph_payload(tmp_indexed_data_repo_with_projects)
    assert len(payload["nodes"]) <= 2
    assert payload["stats"]["trimmed"] >= 1
