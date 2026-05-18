"""4 hard-error project lint rules."""

from __future__ import annotations

from pathlib import Path

from pkm.lint.rules import collect_findings
from pkm.lint.fixers import fix_missing_project_field, fix_category_path_mismatch


def _seed_index(repo: Path, pid: str = "demo") -> None:
    pdir = repo / "data" / "projects" / pid
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:t/t\n"
        "created_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n",
        encoding="utf-8",
    )


def _knowledge_fm(project=None, category=None, source_type="manual"):
    base = ("---\ntitle: x\nslug: 2026-05-07-x\n"
            "created_at: 2026-05-07T00:00:00+09:00\n"
            f"status: draft\nsource_type: {source_type}\nlang: en\n")
    if project is not None:
        base += f"project: {project}\n"
    if category is not None:
        base += f"category: {category}\n"
    base += "---\n\nbody\n"
    return base


def test_missing_project_field(tmp_path):
    _seed_index(tmp_path)
    p = tmp_path / "data" / "projects" / "demo" / "decisions" / "x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_knowledge_fm(category="decisions"), encoding="utf-8")  # NO project field
    issues = collect_findings(tmp_path)
    assert any(i.code == "MISSING_PROJECT_FIELD" for i in issues), [i.code for i in issues]


def test_invalid_category(tmp_path):
    _seed_index(tmp_path)
    p = tmp_path / "data" / "projects" / "demo" / "decisions" / "y.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_knowledge_fm(project="demo", category="bogus"), encoding="utf-8")
    issues = collect_findings(tmp_path)
    assert any(i.code == "INVALID_CATEGORY" for i in issues), [i.code for i in issues]


def test_category_path_mismatch(tmp_path):
    _seed_index(tmp_path)
    p = tmp_path / "data" / "projects" / "demo" / "decisions" / "z.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_knowledge_fm(project="demo", category="pitfalls"), encoding="utf-8")
    issues = collect_findings(tmp_path)
    assert any(i.code == "CATEGORY_PATH_MISMATCH" for i in issues), [i.code for i in issues]


def test_orphan_project_dir(tmp_path):
    pdir = tmp_path / "data" / "projects" / "orphan"
    (pdir / "decisions").mkdir(parents=True)
    issues = collect_findings(tmp_path)
    assert any(i.code == "ORPHAN_PROJECT_DIR" for i in issues), [i.code for i in issues]


def test_fix_missing_project_field(tmp_path):
    _seed_index(tmp_path)
    p = tmp_path / "data" / "projects" / "demo" / "decisions" / "fixme.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_knowledge_fm(category="decisions"), encoding="utf-8")
    issues = collect_findings(tmp_path)
    finding = next(i for i in issues if i.code == "MISSING_PROJECT_FIELD")
    assert fix_missing_project_field(tmp_path, finding)
    # Reload — should now have project: demo
    text = p.read_text(encoding="utf-8")
    assert "project: demo" in text


def test_fix_category_path_mismatch(tmp_path):
    _seed_index(tmp_path)
    p = tmp_path / "data" / "projects" / "demo" / "decisions" / "wrong.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_knowledge_fm(project="demo", category="pitfalls"), encoding="utf-8")
    issues = collect_findings(tmp_path)
    finding = next(i for i in issues if i.code == "CATEGORY_PATH_MISMATCH")
    assert fix_category_path_mismatch(tmp_path, finding)
    text = p.read_text(encoding="utf-8")
    assert "category: decisions" in text
