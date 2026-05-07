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
    """Full initialization: init + migrate + reindex + model cache + claude-code install."""
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
    # M14: simulate `pkm install --for claude-code` so the pkm_install row is OK.
    fake_home = tmp_path / "home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    runner.invoke(
        app,
        ["install", "--for", "claude-code", "--data-repo", str(tmp_path)],
    )


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


def test_doctor_pkm_install_missing(tmp_path: Path, monkeypatch):
    """M14: pkm_install row reports `optional` when HOME has no install."""
    fake_home = tmp_path / "empty-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.output)
    install_item = next(i for i in payload["items"] if i["name"] == "pkm_install")
    assert install_item["status"] == "optional"
    assert "not installed" in (install_item["detail"] or "")


def test_doctor_strict_fails_when_install_missing(tmp_path: Path, monkeypatch):
    """M14: --strict raises PKM_INSTALL_MISSING when HOME has no install (and migrations are applied)."""
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    _init_pkm(tmp_path)
    runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_path)])
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    fake_home = tmp_path / "empty-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    result = runner.invoke(
        app, ["doctor", "--root", str(tmp_path), "--strict", "--json"]
    )
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PKM_INSTALL_MISSING"


def test_doctor_strict_passes_after_install(tmp_path: Path, monkeypatch):
    """M14: install + migrations + reindex + model cache → strict exits 0."""
    _full_init_pkm(tmp_path, monkeypatch)
    result = runner.invoke(
        app, ["doctor", "--root", str(tmp_path), "--strict", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    install_item = next(i for i in payload["items"] if i["name"] == "pkm_install")
    assert install_item["status"] == "ok"


def test_doctor_includes_unprocessed_sessions_row(tmp_path: Path, monkeypatch):
    """M14: pkm doctor reports an unprocessed_sessions info row."""
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.output)
    row = next(i for i in payload["items"] if i["name"] == "unprocessed_sessions")
    assert row["status"] == "info"


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


def test_doctor_includes_projects_row(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = [item["name"] for item in payload["items"]]
    assert "projects" in names
    assert "current_project" in names


def test_doctor_projects_row_zero_when_empty(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.output)
    proj_row = next(it for it in payload["items"] if it["name"] == "projects")
    assert "0 linked" in proj_row.get("detail", "")
    cur_row = next(it for it in payload["items"] if it["name"] == "current_project")
    assert cur_row["status"] in ("info", "ok")  # info if not linked, ok if cwd happens to resolve


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
