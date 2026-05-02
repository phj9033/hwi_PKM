"""Tests for pkm.llm_bridge — Tier 3 hooks + run_task() (M5.3)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pkm.llm_bridge import BridgeError, run_task

FIX = Path(__file__).parent / "fixtures" / "llm_bridge"


def _make_root(tmp_path: Path) -> Path:
    (tmp_path / ".pkm").mkdir()
    return tmp_path


def test_fake_env_short_circuits(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    out = run_task(_make_root(tmp_path), "expand_query", "OAuth")
    assert "OAuth" in out and out.count("\n") == 2


def test_hook_takes_priority_over_config(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    hooks = root / ".pkm" / "hooks"
    hooks.mkdir()
    dst = hooks / "expand_query.sh"
    shutil.copy(FIX / "hook_expand.sh", dst)
    dst.chmod(0o755)

    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.cfgcli]\n"
        f"exec = ['{FIX / 'echo_cli.sh'}', 'fromcfg']\n"
        f"[ai_cli.tasks]\nexpand_query = 'cfgcli'\n",
        encoding="utf-8",
    )

    out = run_task(root, "expand_query", "OAuth")
    assert out == "OAuth | hooked"


def test_config_argv_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.echo]\n"
        f"exec = ['{FIX / 'echo_cli.sh'}', '{{prompt}}']\n"
        f"input = 'arg'\n"
        f"[ai_cli.tasks]\nexpand_query = 'echo'\n",
        encoding="utf-8",
    )
    out = run_task(root, "expand_query", "hello")
    assert out == "ARGV:hello"


def test_config_stdin_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.std]\n"
        f"exec = ['{FIX / 'stdin_cli.sh'}']\n"
        f"input = 'stdin'\n"
        f"[ai_cli.tasks]\nexpand_query = 'std'\n",
        encoding="utf-8",
    )
    out = run_task(root, "expand_query", "hi")
    assert out == "STDIN:hi"


def test_no_resolvable_cli_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(BridgeError, match="No AI CLI"):
        run_task(_make_root(tmp_path), "expand_query", "x")
