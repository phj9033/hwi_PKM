"""Tests for pkm.commands.doctor (M1 scope: structure + python only)."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init_pkm(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])


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


def test_doctor_strict_on_initialized_repo_exits_zero(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert result.exit_code == 0


def test_doctor_json_output_contract(tmp_path: Path):
    """Per spec §5.7: doctor --json must NOT include exec, env, absolute paths,
    or credentials. Whitelist: ok, items[].{name,status,detail}, system.{...}.
    """
    _init_pkm(tmp_path)
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
            assert not item["detail"].startswith("/"), \
                f"absolute path leaked: {item['detail']}"
            assert "Users/" not in item["detail"], \
                f"home dir leaked: {item['detail']}"
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
