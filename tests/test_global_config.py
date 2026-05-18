"""~/.pkm/config.toml — data-repo-location SoT for cross-project pkm CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pkm.config.global_config import (
    GLOBAL_CONFIG_PATH,
    read_global_config,
    write_global_config,
    resolve_data_repo,
    GlobalConfig,
)


def test_resolve_data_repo_prefers_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_DATA_REPO", str(tmp_path))
    assert resolve_data_repo() == tmp_path


def test_resolve_data_repo_falls_back_to_global_config(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    cfg_path = tmp_path / "global-config.toml"
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", cfg_path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(f'data_repo = "{tmp_path}/datarepo"\n', encoding="utf-8")
    (tmp_path / "datarepo").mkdir()
    assert resolve_data_repo() == tmp_path / "datarepo"


def test_resolve_data_repo_falls_back_to_cwd_if_pkm_dir_present(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    (tmp_path / ".pkm").mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_data_repo() == tmp_path


def test_resolve_data_repo_returns_none_when_nothing_resolves(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    monkeypatch.chdir(tmp_path)
    assert resolve_data_repo() is None


def test_write_global_config_creates_parent(tmp_path, monkeypatch):
    cfg_path = tmp_path / "nested" / "config.toml"
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", cfg_path)
    write_global_config(GlobalConfig(data_repo=tmp_path / "repo"))
    assert cfg_path.exists()
    cfg = read_global_config()
    assert cfg.data_repo == tmp_path / "repo"


def test_read_global_config_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    assert read_global_config() is None
