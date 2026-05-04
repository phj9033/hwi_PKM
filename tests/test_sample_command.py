"""Tests for `pkm sample` CLI (M9)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_sample_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=10, with_links=True)
    result = runner.invoke(app, ["sample", "--json", "--seed", "42", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "paths" in payload
    assert "n" in payload
    assert "constraint_relaxed" in payload
    assert 3 <= payload["n"] <= 5
    assert len(payload["paths"]) == payload["n"]
    assert all(p.startswith("data/wiki/") for p in payload["paths"])


def test_sample_text_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=10)
    result = runner.invoke(app, ["sample", "--seed", "42", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    paths = [ln for ln in result.stdout.strip().split("\n") if ln.startswith("data/wiki/")]
    assert 3 <= len(paths) <= 5


def test_sample_seed_reproducible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=10)
    a = runner.invoke(app, ["sample", "--json", "--seed", "7", "--root", str(tmp_path)])
    b = runner.invoke(app, ["sample", "--json", "--seed", "7", "--root", str(tmp_path)])
    assert a.exit_code == 0 and b.exit_code == 0
    assert json.loads(a.stdout)["paths"] == json.loads(b.stdout)["paths"]


def test_sample_insufficient_wiki(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Repo with only 2 wiki docs - below the N_MIN=3 threshold
    seed_wiki_for_search(tmp_path, n=2)
    result = runner.invoke(app, ["sample", "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "SAMPLE_INSUFFICIENT_WIKI" in result.stderr or "wiki 카드" in result.stderr


def test_sample_insufficient_wiki_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=2)
    result = runner.invoke(app, ["sample", "--json", "--root", str(tmp_path)])
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "SAMPLE_INSUFFICIENT_WIKI"


def test_sample_in_help(tmp_path, monkeypatch):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sample" in result.stdout
