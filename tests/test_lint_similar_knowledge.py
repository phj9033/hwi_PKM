"""SIMILAR_KNOWLEDGE_CANDIDATE warning surfaces near-duplicate project knowledge."""

from __future__ import annotations

from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def test_similar_knowledge_emits_warning(tmp_data_repo, monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    pid = "demo"
    pdir = tmp_data_repo / "data" / "projects" / pid
    for cat in ("decisions", "pitfalls", "snippets", "qna", "notes"):
        (pdir / cat).mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:t/t\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n",
        encoding="utf-8",
    )
    base = (
        "---\ntitle: oauth\nslug: 2026-05-07-{slug}\n"
        "created_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\n"
        "source_type: manual\nlang: en\nproject: demo\ncategory: decisions\n"
        "tags: []\n---\n\n"
        "Store OAuth refresh tokens in httpOnly cookies with secure flag.\n"
    )
    (pdir / "decisions" / "2026-05-07-a.md").write_text(
        base.replace("{slug}", "a"), encoding="utf-8"
    )
    (pdir / "decisions" / "2026-05-07-b.md").write_text(
        base.replace("{slug}", "b"), encoding="utf-8"
    )
    runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_data_repo)])
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_data_repo)])

    issues = collect_findings(tmp_data_repo)
    assert any(i.code == "SIMILAR_KNOWLEDGE_CANDIDATE" for i in issues), [i.code for i in issues]
