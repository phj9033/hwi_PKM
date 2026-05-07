"""V3 acceptance test — verifies spec §16.3 M13 criteria end-to-end.

Drives `pkm project link/current/search/related` through real CLI invocations
and asserts behavioral contracts that compose multiple M13 task surfaces.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git") -> None:
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote],
                   cwd=cwd, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------
def test_m003_preserves_v2_search_results():
    """Spec §16.3 M13: m003 적용 후 기존 wiki/raw/writing 검색 결과 ≡ V2.

    Skipped: requires a frozen V2 corpus snapshot to compare against.
    Coverage for additivity is provided indirectly by `test_search_command.py`
    (which still passes after m003) and the smoke check in M13.7.
    """
    pytest.skip("requires frozen V2 corpus snapshot — covered indirectly by existing search tests")


def test_link_idempotent_acceptance(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Spec §16.3 M13: pkm project link 멱등 (재호출 → ALREADY_LINKED, exit 0)."""
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)

    # First link succeeds
    r1 = runner.invoke(app, [
        "project", "link", "--id", "demo", "--no-commit", "--json",
        "--data-repo", str(tmp_data_repo),
    ])
    assert r1.exit_code == 0, r1.output
    p1 = json.loads(r1.output)
    assert p1["ok"] is True

    # Second link with same remote → ALREADY_LINKED, exit 0 (info)
    r2 = runner.invoke(app, [
        "project", "link", "--id", "demo", "--no-commit", "--json",
        "--data-repo", str(tmp_data_repo),
    ])
    assert r2.exit_code == 0, r2.output
    p2 = json.loads(r2.output)
    assert p2.get("error", {}).get("code") == "ALREADY_LINKED"


def test_universal_git_remote_matching(tmp_data_repo, tmp_path, monkeypatch):
    """Spec §16.3 M13: same git remote → same project_id from any cwd.

    Simulates two PCs by creating two distinct cwds that share the same
    canonical remote URL.
    """
    pc_a = tmp_path / "pc-a-checkout"
    pc_b = tmp_path / "pc-b-checkout"
    pc_a.mkdir(); pc_b.mkdir()
    _git_init(pc_a, remote="git@github.com:t/proj.git")
    _git_init(pc_b, remote="https://github.com/t/proj")  # https variant of same remote

    # Link from pc_a
    monkeypatch.chdir(pc_a)
    r1 = runner.invoke(app, [
        "project", "link", "--id", "shared", "--no-commit", "--json",
        "--data-repo", str(tmp_data_repo),
    ])
    assert r1.exit_code == 0, r1.output

    # `current` from pc_b should resolve to the same project via remote normalization
    monkeypatch.chdir(pc_b)
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    r2 = runner.invoke(app, [
        "project", "current", "--json",
        "--data-repo", str(tmp_data_repo),
    ])
    assert r2.exit_code == 0, r2.output
    p2 = json.loads(r2.output)
    assert p2["project_id"] == "shared"


def test_search_scope_project_hard_fails_when_not_linked(
    tmp_indexed_data_repo, tmp_unlinked_cwd, monkeypatch,
):
    """Spec §16.3 M13: --scope project hard-fails (NOT_LINKED) outside any project."""
    monkeypatch.chdir(tmp_unlinked_cwd)
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    result = runner.invoke(app, [
        "search", "oauth", "--scope", "project", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    err = payload.get("error") or {}
    assert err.get("code") == "NOT_LINKED", payload


def test_cwd_linked_default_scope_narrowed(
    tmp_indexed_data_repo, tmp_code_repo, monkeypatch,
):
    """Spec §16.3 M13: cwd-linked 검색 default 가 현재 project 로 좁혀짐."""
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    result = runner.invoke(app, [
        "search", "oauth", "--json",
        "--root", str(tmp_indexed_data_repo),
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    paths = [r["path"] for r in payload["results"]]
    # Default narrows to project:demo, so all hits are under demo
    assert paths
    assert all(p.startswith("data/projects/demo/") for p in paths), paths


def test_all_4_lint_rules_in_failure_matrix():
    """Spec §16.3 M13: 4 hard-error project lint rules registered in matrix."""
    from tests.test_failure_mode_matrix import SCENARIOS
    for code in [
        "MISSING_PROJECT_FIELD",
        "INVALID_CATEGORY",
        "CATEGORY_PATH_MISMATCH",
        "ORPHAN_PROJECT_DIR",
    ]:
        assert code in SCENARIOS, code


def test_all_10_m13_error_codes_defined():
    """Spec §16.3 M13: full error-code surface registered."""
    from pkm.errors import all_error_codes

    actual = all_error_codes()
    for code in [
        "NOT_A_GIT_REPO", "ALREADY_LINKED", "NOT_LINKED",
        "PROJECT_ID_CONFLICT", "INVALID_PROJECT_ID",
        "MISSING_PROJECT_FIELD", "INVALID_CATEGORY", "CATEGORY_PATH_MISMATCH",
        "ORPHAN_PROJECT_DIR", "SIMILAR_KNOWLEDGE_CANDIDATE",
    ]:
        assert code in actual, code


def test_doctor_reports_projects_state(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Spec §16.3 M13: pkm doctor includes projects + current_project rows."""
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "x", "--no-commit", "--json",
                        "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["doctor", "--root", str(tmp_data_repo), "--json"])
    payload = json.loads(result.output)
    names = [it["name"] for it in payload["items"]]
    assert "projects" in names
    assert "current_project" in names
    proj_row = next(it for it in payload["items"] if it["name"] == "projects")
    assert "1 linked" in proj_row.get("detail", "")


def test_knowledge_add_writes_required_frontmatter(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Spec §16.3 M13: knowledge add writes a file with required project/category fields."""
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "demo", "--no-commit", "--json",
                        "--data-repo", str(tmp_data_repo)])
    r = runner.invoke(app, [
        "project", "knowledge", "add",
        "--project", "demo", "--category", "decisions",
        "--slug", "x", "--title", "X",
        "--no-commit", "--json", "--data-repo", str(tmp_data_repo),
    ], input="body\n")
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    f = tmp_data_repo / payload["path"]
    text = f.read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "category: decisions" in text
    # Lint should not flag this file
    from pkm.lint.rules import collect_findings
    findings = collect_findings(tmp_data_repo)
    bad_codes = {"MISSING_PROJECT_FIELD", "INVALID_CATEGORY", "CATEGORY_PATH_MISMATCH"}
    bad = [fnd for fnd in findings if fnd.code in bad_codes and f.name in fnd.path]
    assert not bad, f"freshly-added knowledge tripped lint: {bad}"
