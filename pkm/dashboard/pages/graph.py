"""Build `graph.html` — wiki link graph + suggested-link overlay (vis-network).

The payload is computed in `pkm/dashboard/context.py::_read_graph_payload` and
exposed via `DashboardContext.graph_payload`. This builder serializes that
payload into JSON, embeds it in a `<script id="graph-data">` tag, and lets
`assets/graph.js` initialize vis-network on the client.

Spec reference: 2026-05-06-pkm-v2-design §3.2.
"""

from __future__ import annotations

import json
from pathlib import Path

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.templates import render


def build_graph(out: Path, ctx: DashboardContext) -> Path:
    """Render `graph.html` into `out` and return the written path."""
    payload = ctx.graph_payload
    payload_json = (
        json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
    )
    html = render(
        "graph.html.j2",
        title="graph",
        depth=0,
        payload_json=payload_json,
        unavailable=(payload is None),
    )
    target = out / "graph.html"
    target.write_text(html, encoding="utf-8")
    return target
