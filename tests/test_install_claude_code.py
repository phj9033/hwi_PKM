"""pkm install --for claude-code — global install/uninstall."""

from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_install_creates_global_files(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    result = runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo), "--json"])
    assert result.exit_code == 0, result.output
    # Global config
    assert (tmp_home / ".pkm" / "config.toml").is_file()
    # CLAUDE.md with managed block
    claude_md = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "<!-- pkm:start" in claude_md
    assert "pkm project current" in claude_md
    assert "<!-- pkm:end" in claude_md
    # Slash commands
    for cmd in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        assert (tmp_home / ".claude" / "commands" / cmd).is_file()
    # Skills
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        assert (tmp_home / ".claude" / "skills" / "pkm" / skill / "SKILL.md").is_file()


def test_install_idempotent(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    pre = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    post = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert pre == post


def test_install_preserves_user_content_in_claude_md(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text("# My Custom Header\nUser content here.\n", encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    text = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# My Custom Header" in text
    assert "User content here" in text
    assert "<!-- pkm:start" in text


def test_uninstall_removes_managed_block_only(tmp_data_repo, tmp_home, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_home))
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text("# User\n", encoding="utf-8")
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    # After install: manifest exists and lists installed paths
    assert (tmp_home / ".pkm" / "install_manifest.json").is_file()
    runner.invoke(app, ["install", "--for", "claude-code", "--uninstall"])
    text = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# User" in text
    assert "<!-- pkm:start" not in text
    assert "pkm project current" not in text
    # commands and skills also removed (via manifest)
    assert not (tmp_home / ".claude" / "commands" / "pkm-recall.md").exists()
    assert not (tmp_home / ".claude" / "skills" / "pkm").exists()
    # Manifest itself is deleted after uninstall
    assert not (tmp_home / ".pkm" / "install_manifest.json").exists()


def test_install_files_have_no_html_marker_above_frontmatter(tmp_data_repo, tmp_home, monkeypatch):
    """Critical: Claude Code skill/slash files must start with `---\\n` (frontmatter).
    An HTML comment above would break Claude Code's frontmatter parser.
    """
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(app, ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)])
    for cmd in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        text = (tmp_home / ".claude" / "commands" / cmd).read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{cmd} must start with frontmatter, got: {text[:50]!r}"
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        text = (tmp_home / ".claude" / "skills" / "pkm" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill}/SKILL.md must start with frontmatter, got: {text[:50]!r}"
