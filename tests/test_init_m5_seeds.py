"""M5 init seeding: /ask + /write templates + SCHEMA.md updates."""

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_init_seeds_ask_and_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    cmds_dir = tmp_path / ".claude" / "commands"
    names = sorted(p.name for p in cmds_dir.glob("*.md"))
    assert "ask.md" in names
    assert "write.md" in names
    assert names == sorted(
        [
            "ask.md",
            "blog.md",
            "collect.md",
            "lint.md",
            "promote.md",
            "research.md",
            "review-captures.md",
            "style-import.md",
            "write.md",
        ]
    )


def test_schema_md_documents_ask_and_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "### Ask" in schema
    assert "### Write" in schema
    assert "Chunk → Wiki Synthesis" in schema
    assert "--with-related" in schema
    assert "pkm related" in schema


def test_schema_md_documents_doctor_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "pkm doctor --download" in schema
