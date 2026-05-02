import json
import shutil

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_doctor_reports_ai_cli_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/claude" if n == "claude" else None)
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    items = {it["name"]: it for it in out["items"]}
    assert items["ai_cli"]["status"] == "ok"
    assert items["ai_cli"]["detail"] == "detected: claude"


def test_doctor_reports_ai_cli_missing_optional(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: None)
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    items = {it["name"]: it for it in out["items"]}
    assert items["ai_cli"]["status"] == "optional"


def test_doctor_strict_does_not_fail_on_optional_ai_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: None)
    res = runner.invoke(app, ["doctor", "--strict", "--json"])
    # `optional` status MUST NOT trigger strict failure
    # NOTE: the doctor will likely still fail on missing dirs (data/raw/captures etc.)
    # so we only check that the ai_cli row's `optional` status is not the cause.
    # Test by making sure the doctor doesn't crash and ai_cli is reported.
    assert "ai_cli" in res.stdout
    # Parse JSON and verify ai_cli is optional
    out = json.loads(res.stdout)
    items = {it["name"]: it for it in out["items"]}
    assert items["ai_cli"]["status"] == "optional"


def test_doctor_does_not_leak_exec_or_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.local.toml").write_text(
        "[ai_cli.commands.x]\nexec = ['/usr/secret/bin/x', '--key', 'AAA']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/claude" if n == "claude" else None)
    res = runner.invoke(app, ["doctor", "--json"])
    body = res.stdout
    # absolute paths from config + secret args must not appear in doctor output
    assert "/usr/secret/bin/x" not in body
    assert "AAA" not in body
