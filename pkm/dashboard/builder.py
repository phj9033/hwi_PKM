"""Orchestrator for `pkm dashboard build` — wires every M6 page builder.

`build_dashboard(root, out)` is the single entry point: it builds the
DashboardContext once, then runs each page builder against it, then copies
package assets (style.css, search.js) into ``<out>/assets/``.

Page-build order is deterministic so the output is reproducible:

1. ``index.html`` (landing page)
2. List pages: captures, chunks, wiki, writing
3. Per-doc pages for wiki + writing
4. ``search.html`` + ``search-index.json``
5. ``help.html``
6. ``status.html``
7. Asset copy

Spec reference: M6 plan, Task 11.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pkm.dashboard.context import build_context
from pkm.dashboard.pages.doc import build_doc_page
from pkm.dashboard.pages.help import build_help
from pkm.dashboard.pages.index import build_index
from pkm.dashboard.pages.lists import build_list_page
from pkm.dashboard.pages.search import build_search
from pkm.dashboard.pages.status import build_status

_PKG_ASSETS = Path(__file__).parent / "assets"


def build_dashboard(root: Path, out: Path) -> None:
    """Build the static dashboard for `root` into `out`. Idempotent — safe to
    re-run; existing files are overwritten."""
    out.mkdir(parents=True, exist_ok=True)
    ctx = build_context(root)

    build_index(out, ctx)
    for category in ("captures", "chunks", "wiki", "writing"):
        build_list_page(out, ctx, category)
    for category in ("wiki", "writing"):
        for doc in ctx.registry.docs_by_category.get(category, []):
            build_doc_page(out, ctx, doc)
    build_search(out, ctx)
    build_help(out, ctx)
    build_status(out, ctx)

    _copy_assets(out)


def _copy_assets(out: Path) -> None:
    """Copy package assets (style.css, search.js) into ``<out>/assets/``."""
    dst = out / "assets"
    dst.mkdir(exist_ok=True)
    for src in _PKG_ASSETS.iterdir():
        if src.is_file():
            shutil.copy2(src, dst / src.name)
