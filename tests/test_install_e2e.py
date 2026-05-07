"""End-to-end install verification — manifest contents."""

import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_install_manifest_contains_expected_files(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo), "--json"])
    assert result.exit_code == 0, result.output

    manifest = json.loads((tmp_home / ".pkm" / "install_manifest.json").read_text(encoding="utf-8"))
    paths = manifest["paths"]
    # 4 slash commands + 3 SKILL.md + the reference docs each skill bundle ships.
    skills_dir = tmp_home / ".claude" / "skills" / "pkm"
    expected = {
        str(tmp_home / ".claude" / "commands" / f"{cmd}.md")
        for cmd in ["pkm-recall", "pkm-extract-session", "pkm-backfill", "pkm-project"]
    } | {
        str(skills_dir / skill / "SKILL.md")
        for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]
    } | {
        # M14.6 reference doc.
        str(skills_dir / "recalling-project-context" / "search-scope-guidelines.md"),
        # M14.7 reference docs.
        str(skills_dir / "extracting-session-knowledge" / "extraction-categories.md"),
        str(skills_dir / "extracting-session-knowledge" / "output-schema.md"),
        str(skills_dir / "extracting-session-knowledge" / "review-protocol.md"),
    }
    assert set(paths) == expected, f"unexpected paths in manifest:\n  got: {sorted(paths)}\n  want: {sorted(expected)}"


def test_install_unsupported_target_raises(tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["install", "--for", "codex", "--json"])
    assert result.exit_code != 0
    body = json.loads(result.output)
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
