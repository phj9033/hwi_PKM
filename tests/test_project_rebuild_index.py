"""rebuild_index — deterministic builder for data/projects/<id>/index.md."""

from __future__ import annotations

from pkm.store.project_index import rebuild_index


def _seed_demo(tmp_data_repo, with_decision: bool = True):
    pid = "demo"
    pdir = tmp_data_repo / "data" / "projects" / pid
    (pdir / "decisions").mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:t/t\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n"
        "---\n\nold body\n",
        encoding="utf-8",
    )
    if with_decision:
        (pdir / "decisions" / "2026-05-07-foo.md").write_text(
            "---\ntitle: First Decision\nslug: 2026-05-07-foo\n"
            "created_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\n"
            "source_type: ai_session\nlang: en\nproject: demo\ncategory: decisions\n"
            "---\n\nbody\n",
            encoding="utf-8",
        )
    return pdir


def test_rebuild_index_preserves_frontmatter(tmp_data_repo):
    pdir = _seed_demo(tmp_data_repo)
    rebuild_index(tmp_data_repo, "demo")
    text = (pdir / "index.md").read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "git_remotes:" in text
    assert "First Decision" in text
    assert "old body" not in text


def test_rebuild_index_deterministic(tmp_data_repo):
    """Same corpus → same output."""
    pdir = _seed_demo(tmp_data_repo)
    rebuild_index(tmp_data_repo, "demo")
    first = (pdir / "index.md").read_text(encoding="utf-8")
    rebuild_index(tmp_data_repo, "demo")
    second = (pdir / "index.md").read_text(encoding="utf-8")
    assert first == second


def test_rebuild_index_with_no_categories(tmp_data_repo):
    """Empty project (no decision files) still produces a valid index."""
    pdir = _seed_demo(tmp_data_repo, with_decision=False)
    rebuild_index(tmp_data_repo, "demo")
    text = (pdir / "index.md").read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "# demo" in text  # body title
