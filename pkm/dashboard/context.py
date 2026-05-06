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
import logging
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
_SUBPROCESS_TIMEOUT_S = 30
_logger = logging.getLogger(__name__)


@dataclass
class DashboardContext:
    root: Path
    registry: DocRegistry
    lint_summary: dict[str, Any] | None = None  # parsed `pkm lint --json`
    doctor: dict[str, Any] | None = None  # parsed `pkm doctor --json`
    config_masked: dict[str, Any] | None = None
    recent_log: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[dict[str, Any]] | None = None  # MISSING_LINK_CANDIDATE pairs
    graph_payload: dict[str, Any] | None = None  # M10 graph.html data
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
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pkm", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _logger.warning("pkm %s timed out after %ss", " ".join(args), _SUBPROCESS_TIMEOUT_S)
        return None
    except (subprocess.SubprocessError, OSError) as e:
        _logger.warning("pkm %s failed: %s", " ".join(args), e)
        return None
    out = (result.stdout or "").strip()
    if not out:
        if result.stderr:
            _logger.debug(
                "pkm %s produced empty stdout; stderr: %s",
                " ".join(args),
                result.stderr[:500],
            )
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        _logger.debug("pkm %s stdout was not JSON: %s", " ".join(args), e)
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
        "fixed": int(raw.get("fixed", 0) or 0),
        "ok": bool(raw.get("ok", not (errors or warnings))),
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


def _read_suggestions(root: Path) -> list[dict[str, Any]] | None:
    """Compute MISSING_LINK_CANDIDATE pairs for the dashboard. None means
    "feature unavailable / index missing"; [] means "no suggestions".

    Catches all errors so a malformed index never breaks the dashboard build.
    """
    try:
        from pkm.lint.missing_links import find_suggestions

        sugs = find_suggestions(root)
    except Exception as e:  # noqa: BLE001 — best-effort dashboard input
        _logger.debug("suggestions unavailable: %s", e)
        return None
    return [
        {"src_path": s.src_path, "dst_path": s.dst_path, "similarity": s.similarity}
        for s in sugs
    ]


def _read_graph_config(root: Path) -> dict[str, Any]:
    """Read [dashboard.graph] section, applying defaults."""
    defaults: dict[str, Any] = {
        "max_nodes": 1000,
        "include_writing": False,
        "include_captures": False,
        "overlay_suggestions": True,
    }
    cfg_path = root / ".pkm" / "config.toml"
    if not cfg_path.exists():
        return defaults
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return defaults
    section = (data.get("dashboard") or {}).get("graph") or {}
    out = dict(defaults)
    for k, v in section.items():
        if k in defaults:
            out[k] = v
    return out


def _seed_position(rel_path: str) -> tuple[int, int]:
    """Deterministic initial position from a slug hash. Spread across a 2000x2000 grid."""
    import hashlib

    h = hashlib.sha256(rel_path.encode("utf-8")).digest()
    x = int.from_bytes(h[:4], "big") % 2000 - 1000
    y = int.from_bytes(h[4:8], "big") % 2000 - 1000
    return x, y


def _read_graph_payload(root: Path) -> dict[str, Any] | None:
    """Build the graph payload (nodes/edges/stats/config) for the M10 graph page.

    Returns None when .pkm/index.db is missing — the page renders an
    'unavailable' card in that case. Never raises.
    """
    db_path = root / ".pkm" / "index.db"
    if not db_path.exists():
        return None
    cfg = _read_graph_config(root)
    try:
        from pkm.store.index_db import connect

        conn = connect(root)
    except Exception as e:  # noqa: BLE001
        _logger.debug("graph payload: failed to connect: %s", e)
        return None

    try:
        wanted_buckets = ["wiki"]
        if cfg.get("include_writing"):
            wanted_buckets.append("writing")
        if cfg.get("include_captures"):
            wanted_buckets.append("captures")
        placeholders = ",".join("?" for _ in wanted_buckets)
        rows = conn.execute(
            f"SELECT id, path, bucket, title, status FROM documents "
            f"WHERE bucket IN ({placeholders}) AND status != 'deprecated'",
            wanted_buckets,
        ).fetchall()
        docs = [dict(r) for r in rows]

        cap = int(cfg["max_nodes"])
        trimmed = 0
        if len(docs) > cap:
            edge_count: dict[int, int] = {d["id"]: 0 for d in docs}
            for r in conn.execute(
                "SELECT src_doc_id, dst_doc_id FROM links WHERE dst_doc_id IS NOT NULL"
            ):
                if r["src_doc_id"] in edge_count:
                    edge_count[r["src_doc_id"]] += 1
                if r["dst_doc_id"] in edge_count:
                    edge_count[r["dst_doc_id"]] += 1
            docs.sort(key=lambda d: edge_count.get(d["id"], 0), reverse=True)
            trimmed = len(docs) - cap
            docs = docs[:cap]

        kept_ids = {d["id"] for d in docs}
        nodes = []
        for d in docs:
            x, y = _seed_position(d["path"])
            nodes.append(
                {
                    "id": d["path"],
                    "label": d["title"] or d["path"].rsplit("/", 1)[-1],
                    "group": d["bucket"],
                    "x": x,
                    "y": y,
                }
            )
        path_by_id = {d["id"]: d["path"] for d in docs}

        edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for r in conn.execute(
            "SELECT src_doc_id, dst_doc_id, kind FROM links "
            "WHERE dst_doc_id IS NOT NULL AND kind IN ('wikilink', 'derived_from')"
        ):
            src, dst, kind = r["src_doc_id"], r["dst_doc_id"], r["kind"]
            if src not in kept_ids or dst not in kept_ids:
                continue
            key = (path_by_id[src], path_by_id[dst], kind)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                {"from": path_by_id[src], "to": path_by_id[dst], "type": kind, "weight": 1.0}
            )

        if cfg.get("overlay_suggestions"):
            try:
                from pkm.lint.missing_links import find_suggestions

                node_ids = {n["id"] for n in nodes}
                for s in find_suggestions(root):
                    if s.src_path in node_ids and s.dst_path in node_ids:
                        edges.append(
                            {
                                "from": s.src_path,
                                "to": s.dst_path,
                                "type": "suggested",
                                "weight": s.similarity,
                            }
                        )
            except Exception as e:  # noqa: BLE001
                _logger.debug("graph payload: suggestions overlay failed: %s", e)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "trimmed": trimmed,
            },
            "config": cfg,
        }
    finally:
        conn.close()


def build_context(root: Path) -> DashboardContext:
    """Construct a ``DashboardContext`` for `root`. See module docstring."""
    registry = scan(root)
    lint_raw = _run_pkm_json(["lint", "--json"], cwd=root)
    lint_summary = _adapt_lint(lint_raw if isinstance(lint_raw, dict) else None)
    doctor_raw = _run_pkm_json(["doctor", "--json"], cwd=root)
    doctor = doctor_raw if isinstance(doctor_raw, dict) else None
    config_masked = _read_masked_config(root)
    recent_log = _read_recent_log(root)
    suggestions = _read_suggestions(root)
    graph_payload = _read_graph_payload(root)
    mode = _detect_mode(root)
    return DashboardContext(
        root=root,
        registry=registry,
        lint_summary=lint_summary,
        doctor=doctor,
        config_masked=config_masked,
        recent_log=recent_log,
        suggestions=suggestions,
        graph_payload=graph_payload,
        mode=mode,
    )
