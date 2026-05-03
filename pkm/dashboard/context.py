"""DashboardContext - single object passed to every page builder.

Grown in M6.11; the seed shape lands here so M6.5-M6.10 can build against it.

`build_context(root)` is the production constructor:

1. Walk `data/` to build the doc registry.
2. Run `pkm lint --json` and `pkm doctor --json` via subprocess (each returns
   parsed JSON regardless of exit code — `pkm lint` exits 1 with valid JSON
   on stdout when errors exist, which we still want to display).
3. Adapt the flat lint shape (``{ok, errors:[...], warnings:[...], fixed}``)
   into the nested shape that ``pages/index.py`` consumes
   (``{counts:{errors,warnings}, items:[...]}``).
4. Read `.pkm/config.toml` (NEVER `config.local.toml` — per spec §12) and
   apply the leaf-key secret mask from ``pkm.dashboard._secrets``.
5. Read the last 20 events from `data/log.md` directly via
   ``pkm.store.log.read_events`` (in-process; no subprocess).
6. Detect the dashboard "mode" — currently always ``"strict"`` since the
   spec doesn't define a mode toggle yet. Documented as a deviation point.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pkm.dashboard._secrets import mask
from pkm.dashboard.scanner import DocRegistry, scan
from pkm.store.log import LogEvent, read_events

_RECENT_LOG_LIMIT = 20


@dataclass
class DashboardContext:
    root: Path
    registry: DocRegistry
    lint_summary: dict[str, Any] | None = None  # parsed `pkm lint --json`
    doctor: dict[str, Any] | None = None  # parsed `pkm doctor --json`
    config_masked: dict[str, Any] | None = None
    recent_log: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "strict"


# --------------------------------------------------------------------------- #
# Sub-helpers (private). Tests monkeypatch `_run_pkm_json` to avoid subprocess.
# --------------------------------------------------------------------------- #


def _run_pkm_json(args: list[str], *, cwd: Path) -> dict | list | None:
    """Run ``pkm <args>`` and parse stdout as JSON.

    Note: ``pkm lint --json`` exits 1 when lint errors exist but still emits
    valid JSON on stdout. This helper attempts ``json.loads(stdout)`` regardless
    of exit code; only empty or unparseable stdout returns None.

    Always pass ``--json`` explicitly at the call site
    (e.g. ``_run_pkm_json(["lint", "--json"], cwd=root)``); we do not auto-inject.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    out = (result.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _adapt_lint(raw: dict | None) -> dict | None:
    """Transform ``pkm lint --json``'s flat shape into the nested shape that
    ``pages/index.py`` expects.

    Input  (flat, from `pkm/commands/lint.py`):
        {"ok": bool, "errors": [...], "warnings": [...], "fixed": int}
    Output (nested, consumed by ``index.html.j2`` via `_lint_view`):
        {"counts": {"errors": int, "warnings": int}, "items": [...]}

    Each item already carries ``code``, ``severity``, ``path``, ``message``,
    ``field``, ``fixable`` from the lint command, so we merge errors+warnings
    into a single ``items`` list and let ``_lint_view`` count by ``code``.
    """
    if raw is None:
        return None
    errors = raw.get("errors") or []
    warnings = raw.get("warnings") or []
    return {
        "counts": {
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "items": [*errors, *warnings],
    }


def _read_masked_config(root: Path) -> dict[str, Any] | None:
    """Read `<root>/.pkm/config.toml` and return a deep-masked copy.

    Per spec §12, `.pkm/config.local.toml` is *never* read by the dashboard.
    Returns ``None`` if the file is missing or fails to parse — the dashboard
    is best-effort and shouldn't blow up on a malformed config.
    """
    cfg_path = root / ".pkm" / "config.toml"
    if not cfg_path.exists():
        return None
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return mask(data)


def _event_to_dict(ev: LogEvent) -> dict[str, Any]:
    """Project a `LogEvent` into the dict shape `index.html.j2` consumes
    (``{at, type, ref, message}``). The template uses Jinja attribute access
    which falls back to ``["key"]`` for dicts."""
    return {
        "at": ev.timestamp or "",
        "type": ev.type,
        "ref": ev.ref,
        "message": ev.message,
    }


def _read_recent_log(root: Path, *, limit: int = _RECENT_LOG_LIMIT) -> list[dict[str, Any]]:
    """Return the last ``limit`` events from ``data/log.md``, most-recent-first.

    Reads via ``pkm.store.log.read_events`` (in-process, faster than spawning
    a subprocess). The log is append-only and chronological, so we tail and
    reverse.
    """
    events = read_events(root)
    if not events:
        return []
    tail = events[-limit:]
    tail.reverse()
    return [_event_to_dict(e) for e in tail]


def _detect_mode(root: Path) -> str:
    """Return the dashboard "mode" string.

    The spec doesn't currently define a mode toggle; ``pages/status.py`` only
    renders the value as a label. Always returns ``"strict"`` — this matches
    `DashboardContext`'s default and keeps the page deterministic. The ``root``
    parameter is reserved for when the spec grows a mode field (e.g. in
    `.pkm/config.toml`); wiring lands then.
    """
    del root  # unused (reserved for future config wiring)
    return "strict"


def build_context(root: Path) -> DashboardContext:
    """Construct a ``DashboardContext`` for `root`. See module docstring."""
    registry = scan(root)
    lint_raw = _run_pkm_json(["lint", "--json"], cwd=root)
    lint_summary = _adapt_lint(lint_raw if isinstance(lint_raw, dict) else None)
    doctor_raw = _run_pkm_json(["doctor", "--json"], cwd=root)
    doctor = doctor_raw if isinstance(doctor_raw, dict) else None
    config_masked = _read_masked_config(root)
    recent_log = _read_recent_log(root)
    mode = _detect_mode(root)
    return DashboardContext(
        root=root,
        registry=registry,
        lint_summary=lint_summary,
        doctor=doctor,
        config_masked=config_masked,
        recent_log=recent_log,
        mode=mode,
    )
