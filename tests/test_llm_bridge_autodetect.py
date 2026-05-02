"""Tests for pkm.llm_bridge — Tier 1 PATH autodetect (M5.1)."""

from __future__ import annotations

import dataclasses
import shutil

import pytest

from pkm.llm_bridge import _DETECT_ORDER, DetectedCLI, detect_ai_cli


def test_detect_returns_first_in_order(monkeypatch: pytest.MonkeyPatch):
    table = {"claude": "/usr/bin/claude", "gemini": "/usr/bin/gemini"}
    monkeypatch.setattr(shutil, "which", lambda n: table.get(n))
    out = detect_ai_cli()
    assert out == DetectedCLI(name="claude", path="/usr/bin/claude")


def test_detect_skips_missing_then_finds(monkeypatch: pytest.MonkeyPatch):
    table = {"gemini": "/opt/gemini"}  # claude + codex missing
    monkeypatch.setattr(shutil, "which", lambda n: table.get(n))
    out = detect_ai_cli()
    assert out and out.name == "gemini"


def test_detect_returns_none_when_all_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(shutil, "which", lambda n: None)
    assert detect_ai_cli() is None


def test_detect_order_is_spec_order():
    assert _DETECT_ORDER == ("claude", "codex", "gemini", "ollama")


def test_detected_cli_is_frozen():
    d = DetectedCLI(name="claude", path="/x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.name = "codex"  # type: ignore[misc]
