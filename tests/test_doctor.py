"""Tests for pkm.commands.doctor (M1 scope: structure + python only)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init_pkm(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def _full_init_pkm(tmp_path: Path, monkeypatch) -> None:
    """Full initialization: init + migrate + reindex + model cache stub for M3+ items."""
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_path)])
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    # Seed the HF standard cache layout so `pkm.store.model_cache.is_cached`
    # treats bge-m3 as present (mirrors what `snapshot_download` writes).
    model_cache = tmp_path / "cache"
    snapshot = model_cache / "models--BAAI--bge-m3" / "snapshots" / "stub"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    monkeypatch.setenv("PKM_MODEL_CACHE", str(model_cache))


def test_doctor_on_initialized_repo_passes(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0
    # All structure items expected to be OK
    assert "data/" in result.output
    assert "OK" in result.output


def test_doctor_on_empty_dir_reports_missing_but_exits_zero(tmp_path: Path):
    """Per spec §5.7: doctor default = exit 0 even when items missing."""
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0  # default = informative, not gate
    assert "MISSING" in result.output or "missing" in result.output.lower()


def test_doctor_strict_mode_exits_nonzero_on_missing(tmp_path: Path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert result.exit_code != 0


def test_doctor_strict_on_initialized_repo_exits_zero(tmp_path: Path, monkeypatch):
    # M3: full init (init + reindex + model cache) required for strict mode to pass
    _full_init_pkm(tmp_path, monkeypatch)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert result.exit_code == 0


def test_doctor_json_output_contract(tmp_path: Path, monkeypatch):
    """Per spec §5.7: doctor --json must NOT include exec, env, absolute paths,
    or credentials. Whitelist: ok, items[].{name,status,detail}, system.{...}.
    """
    # M3: full init (init + reindex + model cache) required for payload["ok"] True
    _full_init_pkm(tmp_path, monkeypatch)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "items" in payload
    assert isinstance(payload["items"], list)
    for item in payload["items"]:
        assert set(item.keys()) <= {"name", "status", "detail"}
        # No absolute paths in detail
        if item["detail"]:
            assert not item["detail"].startswith("/"), f"absolute path leaked: {item['detail']}"
            assert "Users/" not in item["detail"], f"home dir leaked: {item['detail']}"
            assert "exec" not in item["detail"].lower()
    # System block — only allowed numeric/derived fields
    if "system" in payload:
        allowed = {"ram_total_gb", "ram_available_gb", "recommended_batch_size", "python_version"}
        assert set(payload["system"].keys()) <= allowed


def test_doctor_python_version_check(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.output)
    py_items = [i for i in payload["items"] if i["name"] == "python"]
    assert len(py_items) == 1
    assert py_items[0]["status"] == "ok"


def test_doctor_shows_schema_version(tmp_path: Path):
    """M12: doctor reports schema_version row."""
    _init_pkm(tmp_path)
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = [it["name"] for it in payload["items"]]
    assert "schema_version" in names


def test_doctor_shows_tokenizer(tmp_path: Path):
    """M12: doctor reports tokenizer row."""
    _init_pkm(tmp_path)
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = [it["name"] for it in payload["items"]]
    assert "tokenizer" in names


def test_doctor_strict_fails_on_pending_migration(tmp_path: Path):
    """M12: --strict surfaces MIGRATION_PENDING when schema_version below latest."""
    _init_pkm(tmp_path)
    from pkm.store.index_db import connect

    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    res = runner.invoke(app, ["doctor", "--strict", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload.get("error", {}).get("code") == "MIGRATION_PENDING"
