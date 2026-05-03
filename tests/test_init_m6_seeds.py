"""M6 init seeding: SCHEMA.md documents the dashboard + bootstrap commands."""

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_schema_md_documents_dashboard_build(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "pkm dashboard build" in schema


def test_schema_md_documents_bootstrap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "pkm bootstrap" in schema


def test_schema_md_has_browse_dashboard_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "### Browse the dashboard" in schema
    assert "dashboard/index.html" in schema
