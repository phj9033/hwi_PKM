"""Smoke tests for `pkm adapter ...` CLI surface.

We don't hit real networks — we monkeypatch the underlying fetchers and
verify the CLI wires arguments and errors through correctly.
"""

from __future__ import annotations

import subprocess

from typer.testing import CliRunner

from pkm.cli import app


def test_adapter_jina_calls_fetch(monkeypatch):
    captured = {}

    def fake_fetch(url, **kw):
        captured["url"] = url
        return "JINA-BODY"

    monkeypatch.setattr("pkm.adapters.jina.fetch_markdown", fake_fetch)
    result = CliRunner().invoke(app, ["adapter", "jina", "https://example.com/"])
    assert result.exit_code == 0, result.output
    assert "JINA-BODY" in result.output
    assert captured["url"] == "https://example.com/"


def test_adapter_auto_routes_youtube(monkeypatch):
    monkeypatch.setattr("pkm.adapters.youtube.fetch", lambda url: "YT-MD")
    result = CliRunner().invoke(app, ["adapter", "auto", "https://www.youtube.com/watch?v=x"])
    assert result.exit_code == 0
    assert "YT-MD" in result.output


def test_adapter_auto_routes_openalex(monkeypatch):
    monkeypatch.setattr("pkm.adapters.openalex.fetch", lambda url: "OA-MD")
    result = CliRunner().invoke(app, ["adapter", "auto", "https://arxiv.org/abs/2310.06770"])
    assert result.exit_code == 0
    assert "OA-MD" in result.output


def test_adapter_auto_falls_back_to_jina(monkeypatch):
    monkeypatch.setattr("pkm.adapters.jina.fetch_markdown", lambda url, **kw: "JINA-FB")
    result = CliRunner().invoke(app, ["adapter", "auto", "https://martinfowler.com/x"])
    assert result.exit_code == 0
    assert "JINA-FB" in result.output


def test_adapter_hn_silently_empty_on_no_discussion(monkeypatch):
    monkeypatch.setattr("pkm.adapters.hn.discussions", lambda url, **kw: "")
    result = CliRunner().invoke(app, ["adapter", "hn", "https://example.com/"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_adapter_jina_propagates_error(monkeypatch):
    from pkm.adapters.jina import JinaError

    def boom(url, **kw):
        raise JinaError("network down")

    monkeypatch.setattr("pkm.adapters.jina.fetch_markdown", boom)
    result = CliRunner().invoke(app, ["adapter", "jina", "https://example.com/"])
    assert result.exit_code == 1
    assert "JINA_ERROR" in result.output or "Error" in result.output
