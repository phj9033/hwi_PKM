"""Build `status.html` — doctor checklist + masked config + mode.

Three sections, all presentation-only (no business logic):

1. **Doctor report** — renders ``ctx.doctor`` (parsed from ``pkm doctor --json``)
   as a checklist with ``✓`` (status == "ok") or ``✗`` for everything else.
   The real JSON shape, per ``pkm/commands/doctor.py``, is::

       {"ok": bool,
        "items": [{"name": str, "status": "ok"|"missing"|"error"|"optional",
                    "detail": str|None}, ...],
        "system": {...}}

   When ``ctx.doctor is None`` we render ``(unavailable — run pkm doctor)``.

2. **Config** — renders ``ctx.config_masked`` as a flat dot-notation
   definition list. The dict is *already masked* upstream (``builder.py``,
   landing in M6.11). This page never re-masks; doing so would risk double-
   masking and would duplicate the regex that lives in ``_secrets.py``.

3. **Mode** — string from ``ctx.mode`` (defaults to ``"strict"``).

Spec reference: M6 plan, Task 10.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.templates import render


def _doctor_view(doctor: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Project ``ctx.doctor`` into the per-item checklist the template wants.

    Returns ``None`` when no doctor payload is available so the template can
    render the "(unavailable …)" placeholder. Each rendered entry carries an
    explicit ``ok`` flag (``status == "ok"``) plus the original ``status`` and
    ``detail`` for display.
    """
    if doctor is None:
        return None
    items = doctor.get("items") or []
    view: list[dict[str, Any]] = []
    for it in items:
        status = it.get("status", "")
        view.append(
            {
                "name": it.get("name", ""),
                "status": status,
                "ok": status == "ok",
                "detail": it.get("detail") or "",
            }
        )
    return view


def _flatten_config(d: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested dicts into ``[("a.b.c", value), ...]`` pairs.

    Lists/tuples and scalars are emitted verbatim — only nested dicts get
    walked. Order follows ``dict`` insertion order so the rendered config
    table mirrors the source TOML layout.
    """
    rows: list[tuple[str, Any]] = []
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            rows.extend(_flatten_config(v, key))
        else:
            rows.append((key, v))
    return rows


def _config_view(config_masked: dict[str, Any] | None) -> list[tuple[str, Any]] | None:
    if config_masked is None:
        return None
    return _flatten_config(config_masked)


def build_status(out: Path, ctx: DashboardContext) -> Path:
    """Render ``status.html`` into ``out`` and return the written path."""
    out.mkdir(parents=True, exist_ok=True)

    html = render(
        "status.html.j2",
        title="status",
        depth=0,
        doctor_items=_doctor_view(ctx.doctor),
        config_rows=_config_view(ctx.config_masked),
        mode=ctx.mode,
    )
    target = out / "status.html"
    target.write_text(html, encoding="utf-8")
    return target
