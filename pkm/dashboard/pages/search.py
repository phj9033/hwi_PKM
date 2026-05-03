"""Build `search.html` + `search-index.json` at the dashboard root.

The page is a thin shell — it embeds an `<input id="q">`, an `<input id="tag">`,
and a `<ul id="results">`. The actual filter/render logic is the vanilla-JS
client at ``pkm/dashboard/assets/search.js``, which fetches
``search-index.json`` (sibling file at ``out/search-index.json``) and renders
the top-50 matches.

JSON shape (locked — clients depend on these exact keys):

    [
      {"title": str, "path": str, "slug": str, "tags": list[str],
       "status": str, "bucket": str, "snippet": str, "url": str},
      ...
    ]

- ``path``  — ``Doc.rel_path`` (no ``data/`` prefix).
- ``url``   — ``Doc.url_path`` for wiki/writing; ``""`` for captures + chunks
  so the client renders them as plain text (no doc page exists).
- ``snippet`` — first 200 chars of body (post-frontmatter), with leading
  whitespace stripped *before* slicing so the visible length stays stable.
- ``bucket`` — string; falls back to ``""`` when the doc has no bucket
  (captures, chunks, writing).

Spec reference: §7 (dashboard) — search page.
"""

from __future__ import annotations

import json
from pathlib import Path

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.scanner import Doc
from pkm.dashboard.templates import render

_SNIPPET_LEN = 200


def _snippet(body: str) -> str:
    """First 200 chars of the body, leading whitespace stripped."""
    return (body or "").lstrip()[:_SNIPPET_LEN]


def _entry(doc: Doc) -> dict:
    url = doc.url_path if doc.category in ("wiki", "writing") else ""
    return {
        "title": doc.title,
        "path": doc.rel_path,
        "slug": doc.slug or "",
        "tags": list(doc.tags),
        "status": doc.status or "",
        "bucket": doc.bucket or "",
        "snippet": _snippet(doc.body),
        "url": url,
    }


def _all_docs(ctx: DashboardContext) -> list[Doc]:
    docs: list[Doc] = []
    for category in ("captures", "chunks", "wiki", "writing"):
        docs.extend(ctx.registry.docs_by_category.get(category, []))
    return docs


def build_search(out: Path, ctx: DashboardContext) -> tuple[Path, Path]:
    """Render ``search.html`` + ``search-index.json`` into ``out``.

    Returns ``(html_path, json_path)``.
    """
    out.mkdir(parents=True, exist_ok=True)

    index = [_entry(d) for d in _all_docs(ctx)]
    json_path = out / "search-index.json"
    json_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    html = render("search.html.j2", title="search", depth=0)
    html_path = out / "search.html"
    html_path.write_text(html, encoding="utf-8")

    return html_path, json_path
