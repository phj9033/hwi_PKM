"""Build `index.html` — landing page with stat strip, lint summary, recent log.

Spec reference: §7 (dashboard).

The page consumes `DashboardContext` and is independent of M3/M4 internals
beyond what the scanner already exposed. Lint and log inputs are optional;
when missing, the corresponding card renders an `empty` placeholder.

Lint summary contract (consumed here, populated in M6.11 by the builder):

    {
      "counts":  {"errors": int, "warnings": int, "info": int},
      "items":   [{"code": str, "severity": str, "path": str, ...}, ...]
    }

The real `pkm lint --json` shape is currently flat (`errors: [...]` /
`warnings: [...]`). M6.11 will adapt that shape into the contract above.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.templates import render

_LOG_TAIL = 20


def _counts(ctx: DashboardContext) -> dict[str, int]:
    by_cat = ctx.registry.docs_by_category
    return {
        "captures": len(by_cat.get("captures", [])),
        "chunks": len(by_cat.get("chunks", [])),
        "wiki": len(by_cat.get("wiki", [])),
        "writing": len(by_cat.get("writing", [])),
    }


def _lint_view(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Project the spec'd lint shape into a flat view for the template.

    Returns None if `summary` is None (unavailable).
    """
    if summary is None:
        return None
    counts = summary.get("counts") or {}
    items = summary.get("items") or []
    code_counter: Counter[str] = Counter()
    for it in items:
        code = it.get("code")
        if isinstance(code, str) and code:
            code_counter[code] += 1
    return {
        "errors": int(counts.get("errors", 0)),
        "warnings": int(counts.get("warnings", 0)),
        "info": int(counts.get("info", 0)),
        "top_codes": code_counter.most_common(3),
    }


_SUGGESTIONS_LIMIT = 20


def _suggestions_view(items: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Cap to top-N for the landing page; `None` means feature unavailable."""
    if items is None:
        return None
    return list(items[:_SUGGESTIONS_LIMIT])


def build_index(out: Path, ctx: DashboardContext) -> Path:
    """Render `index.html` into `out` and return the written path."""
    html = render(
        "index.html.j2",
        title="index",
        depth=0,
        counts=_counts(ctx),
        lint=_lint_view(ctx.lint_summary),
        suggestions=_suggestions_view(ctx.suggestions),
        recent_log=list(ctx.recent_log[-_LOG_TAIL:]),
    )
    target = out / "index.html"
    target.write_text(html, encoding="utf-8")
    return target
