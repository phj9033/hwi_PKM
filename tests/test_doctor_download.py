"""Tests for pkm doctor --download (M5.5 scope: model cache snapshot fetcher)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_download_returns_stub_results_under_test(tmp_path, monkeypatch):
    """With PKM_TEST_SKIP_DOWNLOAD=1 (set in conftest), --download returns stub results."""
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["doctor", "--download", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["ok"] is True
    names = [m["name"] for m in out["models"]]
    assert "BAAI/bge-m3" in names and "BAAI/bge-reranker-v2-m3" in names
    for m in out["models"]:
        assert m["cached"] is True  # stub path always reports cached


def test_download_text_output(tmp_path, monkeypatch):
    """Text output of --download lists models and cache dir."""
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["doctor", "--download"])
    assert res.exit_code == 0
    assert "BAAI/bge-m3" in res.stdout
    assert "BAAI/bge-reranker-v2-m3" in res.stdout


def test_download_skips_status_report(tmp_path, monkeypatch):
    """When --download is set, doctor short-circuits and DOES NOT include `items`."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    res = runner.invoke(app, ["doctor", "--download", "--json"])
    out = json.loads(res.stdout)
    # When --download is set, doctor short-circuits and DOES NOT include `items`
    assert "items" not in out


def test_default_doctor_does_not_download(tmp_path, monkeypatch):
    """Default doctor (without --download) runs status report, not download."""
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    assert "items" in out  # default path = status report
    assert "models" not in out
