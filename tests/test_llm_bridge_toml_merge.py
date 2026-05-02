"""Tests for pkm.llm_bridge — Tier 2 TOML merge + schema validation (M5.2)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from pkm.llm_bridge import BridgeConfigError, load_config

FIX = Path(__file__).parent / "fixtures" / "llm_bridge"


def _setup(tmp_path: Path, commit: str | None, local: str | None) -> Path:
    """Set up a temporary .pkm directory with optional config files."""
    pkm_dir = tmp_path / ".pkm"
    pkm_dir.mkdir()
    if commit:
        shutil.copy(FIX / commit, pkm_dir / "config.toml")
    if local:
        shutil.copy(FIX / local, pkm_dir / "config.local.toml")
    return tmp_path


def test_load_returns_empty_when_no_files(tmp_path):
    """load_config returns empty BridgeConfig when no files exist."""
    cfg = load_config(tmp_path)
    assert cfg.default is None
    assert cfg.commands == {}
    assert cfg.tasks == {}


def test_load_merges_commit_and_local(tmp_path):
    """load_config merges config.toml and config.local.toml correctly."""
    root = _setup(tmp_path, "config_commit_ok.toml", "config_local_ok.toml")
    cfg = load_config(root)
    assert cfg.default == "my-claude"
    assert cfg.fallback_order == ("my-claude", "ollama-local")
    assert "my-claude" in cfg.commands and "ollama-local" in cfg.commands
    assert cfg.tasks == {"expand_query": "ollama-local"}


def test_local_overrides_commit_for_same_alias(tmp_path):
    """Local config overrides commit config at the same key."""
    pkm = tmp_path / ".pkm"
    pkm.mkdir()
    (pkm / "config.toml").write_text(
        "[ai_cli]\ndefault = 'a'\n", encoding="utf-8"
    )
    (pkm / "config.local.toml").write_text(
        "[ai_cli]\ndefault = 'b'\n[ai_cli.commands.b]\nexec = ['echo']\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.default == "b"


def test_exec_in_commit_config_is_rejected(tmp_path):
    """exec key in config.toml (commit) is rejected."""
    root = _setup(tmp_path, "config_commit_bad_exec.toml", None)
    with pytest.raises(BridgeConfigError, match=re.escape("config.local.toml")):
        load_config(root)


def test_secret_pattern_in_commit_config_is_rejected(tmp_path):
    """Credential patterns in config.toml (commit) are rejected."""
    root = _setup(tmp_path, "config_commit_bad_secret.toml", None)
    with pytest.raises(BridgeConfigError, match="secret"):
        load_config(root)


def test_local_only_works(tmp_path):
    """load_config works with only config.local.toml (no config.toml)."""
    root = _setup(tmp_path, None, "config_local_ok.toml")
    cfg = load_config(root)
    assert "my-claude" in cfg.commands


def test_cli_spec_requires_exec(tmp_path):
    """CLISpec without exec raises BridgeConfigError."""
    pkm = tmp_path / ".pkm"
    pkm.mkdir()
    (pkm / "config.local.toml").write_text(
        "[ai_cli.commands.broken]\ninput = 'arg'\n", encoding="utf-8"
    )
    with pytest.raises(BridgeConfigError, match="exec"):
        load_config(tmp_path)
