"""Tests for pkm/dashboard/pages/status.py — status.html (doctor + config + mode).

The page is presentation-only:

- ``ctx.doctor`` is the parsed ``pkm doctor --json`` payload (see
  ``pkm/commands/doctor.py``). Real shape is
  ``{"ok": bool, "items": [{"name", "status", "detail"}, ...], "system": {...}}``.
  Per-item ``status`` is one of ``ok | missing | error | optional``.
- ``ctx.config_masked`` is *already masked* by the upstream ``builder.py``;
  the page never re-masks. The secret-config fixture below applies
  ``pkm.dashboard._secrets.mask`` itself, mirroring that contract.
- ``ctx.mode`` defaults to ``"strict"`` on ``DashboardContext``.
"""

from __future__ import annotations

import pytest

from pkm.dashboard._secrets import mask
from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.status import build_status
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


@pytest.fixture
def ctx_with_doctor(ctx_seeded):
    ctx_seeded.doctor = {
        "ok": True,
        "items": [
            {"name": "python", "status": "ok", "detail": "3.13.0"},
            {"name": "data/raw/captures", "status": "ok", "detail": None},
            {"name": "ai_cli", "status": "optional", "detail": "no ai cli on PATH"},
        ],
        "system": {"python_version": "3.13"},
    }
    return ctx_seeded


@pytest.fixture
def ctx_no_doctor(ctx_seeded):
    ctx_seeded.doctor = None
    return ctx_seeded


@pytest.fixture
def ctx_with_secret_config(ctx_seeded):
    # Mask runs in the fixture so the page stays presentation-only.
    ctx_seeded.config_masked = mask(
        {
            "ai": {"openai_api_token": "supersecret"},
            "core": {"verbosity": "info"},
        }
    )
    return ctx_seeded


def test_status_renders_doctor_checklist(tmp_path, ctx_with_doctor):
    p = build_status(tmp_path / "out", ctx_with_doctor)
    html = p.read_text(encoding="utf-8")
    assert "✓" in html or "✗" in html
    assert "python" in html.lower()


def test_status_doctor_unavailable(tmp_path, ctx_no_doctor):
    p = build_status(tmp_path / "out", ctx_no_doctor)
    assert "(unavailable" in p.read_text(encoding="utf-8")


def test_status_config_secrets_masked(tmp_path, ctx_with_secret_config):
    p = build_status(tmp_path / "out", ctx_with_secret_config)
    html = p.read_text(encoding="utf-8")
    assert "***" in html
    assert "supersecret" not in html


def test_status_mode_displayed(tmp_path, ctx_with_doctor):
    p = build_status(tmp_path / "out", ctx_with_doctor)
    assert "strict" in p.read_text(encoding="utf-8")
