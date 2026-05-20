from __future__ import annotations

from typer.testing import CliRunner

from pkm.cli import app


def test_enrich_tldr_fake(monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    runner = CliRunner()
    result = runner.invoke(app, ["enrich", "tldr"], input="some body text\n")
    assert result.exit_code == 0, result.output
    assert "FAKE-TLDR" in result.output


def test_enrich_tags_fake(monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    runner = CliRunner()
    result = runner.invoke(app, ["enrich", "tags"], input="some body text\n")
    assert result.exit_code == 0, result.output
    assert "fake-tag-a" in result.output and "fake-tag-b" in result.output


def test_enrich_related_fake(monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    runner = CliRunner()
    result = runner.invoke(app, ["enrich", "related"], input="some body text\n")
    assert result.exit_code == 0, result.output
    assert "wiki-slug-a" in result.output


def test_enrich_empty_body_returns_empty(monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    runner = CliRunner()
    result = runner.invoke(app, ["enrich", "tldr"], input="   \n")
    assert result.exit_code == 0
    assert result.output.strip() == ""
