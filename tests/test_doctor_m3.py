"""Tests for M3 additions to `pkm doctor`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold_full(root: Path):
    """Scaffold that satisfies M1 doctor (init layout) + M3 (after reindex).

    Uses the public CLI to avoid coupling to private symbols in pkm.commands.init.
    """
    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(root)])
    assert res.exit_code == 0, res.output


def test_doctor_lists_index_and_model_items(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "fake_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = {it["name"] for it in payload["items"]}
    assert "index.db" in names
    assert "bge-m3" in names


def test_doctor_strict_fails_when_model_missing(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "missing_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert res.exit_code != 0


def test_doctor_default_exit_zero_even_when_missing(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "missing_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert res.exit_code == 0


def test_doctor_download_invokes_snapshot(tmp_path: Path, monkeypatch):
    """--download triggers huggingface_hub.snapshot_download (mocked)."""
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "cache"))
    called: dict = {}

    def fake_snapshot(repo_id, **kwargs):
        called["repo_id"] = repo_id
        cache_dir = kwargs.get("cache_dir") or kwargs.get("local_dir")
        assert cache_dir is not None
        cache = Path(cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "config.json").write_text("{}")
        return str(cache)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot)

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--download"])
    assert res.exit_code == 0
    assert called["repo_id"] == "BAAI/bge-m3"


def test_doctor_lists_git_item(tmp_path: Path):
    runner = CliRunner()
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = {it["name"] for it in payload["items"]}
    assert "git" in names
    git_item = next(it for it in payload["items"] if it["name"] == "git")
    assert git_item["status"] == "ok"


def test_doctor_strict_fails_when_not_a_git_repo(tmp_path: Path, monkeypatch):
    """Bare scaffold without git_init → --strict should fail."""
    # Build minimal scaffold without going through pkm init (which now does git init).
    (tmp_path / "data" / "log.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "log.md").write_text("", encoding="utf-8")
    (tmp_path / "data" / "index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "notes").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "reports").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "writing").mkdir(parents=True)
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.toml").write_text("", encoding="utf-8")
    (tmp_path / "SCHEMA.md").write_text("# SCHEMA\n", encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / ".cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert res.exit_code != 0
