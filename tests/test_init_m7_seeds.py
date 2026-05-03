"""M7 init seeding: SCHEMA.md documents `pkm bench` + the failure-code contract."""

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_schema_md_documents_bench(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "pkm bench" in schema


def test_schema_md_documents_failure_codes_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "Failure codes" in schema
    # The section anchors on PKMError + the JSON shape it documents.
    assert "PKMError" in schema
    assert '"ok": false' in schema
