"""Build per-category list pages: `captures.html`, `chunks.html`, `wiki.html`,
`writing.html`.

A single template (`list.html.j2`) is parameterized by a `columns` spec and a
list of `rows` (plain dicts). The Python side derives:

- `topic` for chunks (parent folder name from `rel_path`),
- `sources_count` from the chunk frontmatter `sources` list,
- `derived_count` for writing from frontmatter `derived_from`,
- `url_path` (carried straight from `Doc.url_path`) so the template can wrap
  title/slug cells in `<a>` only for wiki + writing (for which scanner sets
  `url_path` to a non-empty string).

Filter bar (input + status select) is client-side only; no filter state is
threaded through the build pipeline.

Spec reference: §7 (dashboard) — list pages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.scanner import Doc
from pkm.dashboard.templates import render

_CATEGORIES: tuple[str, ...] = ("captures", "chunks", "wiki", "writing")


def _columns_for(category: str) -> list[dict]:
    """Return the column spec for a given category.

    Each column is `{"key": str, "label": str, "linkable": bool?}`.
    `linkable` (default False) tells the template to wrap the cell in an `<a>`
    when `row.url_path` is non-empty.
    """
    if category == "captures":
        return [
            {"key": "title", "label": "Title"},
            {"key": "slug", "label": "Slug"},
            {"key": "status", "label": "Status"},
            {"key": "lang", "label": "Lang"},
            {"key": "tags", "label": "Tags"},
            {"key": "source_url", "label": "Source"},
        ]
    if category == "chunks":
        return [
            {"key": "topic", "label": "Topic"},
            {"key": "status", "label": "Status"},
            {"key": "lang", "label": "Lang"},
            {"key": "sources_count", "label": "Sources"},
        ]
    if category == "wiki":
        return [
            {"key": "title", "label": "Title", "linkable": True},
            {"key": "slug", "label": "Slug", "linkable": True},
            {"key": "bucket", "label": "Bucket"},
            {"key": "status", "label": "Status"},
            {"key": "lang", "label": "Lang"},
            {"key": "tags", "label": "Tags"},
        ]
    if category == "writing":
        return [
            {"key": "title", "label": "Title", "linkable": True},
            {"key": "slug", "label": "Slug", "linkable": True},
            {"key": "status", "label": "Status"},
            {"key": "lang", "label": "Lang"},
            {"key": "derived_count", "label": "Derived"},
            {"key": "tags", "label": "Tags"},
        ]
    raise ValueError(f"unknown category: {category}")


def _topic_from_rel(rel_path: str) -> str:
    """`raw/chunks/oauth/README.md` → `oauth` (parent folder name)."""
    parts = rel_path.split("/")
    if len(parts) >= 2:
        return parts[-2]
    return ""


def _row_for(doc: Doc, category: str) -> dict[str, Any]:
    """Project a `Doc` into a flat row dict the template iterates."""
    fm = doc.frontmatter or {}
    base: dict[str, Any] = {
        "title": doc.title,
        "slug": doc.slug or "",
        "status": doc.status or "",
        "lang": doc.lang or "",
        "tags": ", ".join(doc.tags),
        "url_path": doc.url_path,
    }
    if category == "captures":
        src = fm.get("source_url")
        base["source_url"] = src if isinstance(src, str) else ""
        return base
    if category == "chunks":
        sources = fm.get("sources") or []
        base["topic"] = _topic_from_rel(doc.rel_path)
        base["sources_count"] = len(sources) if isinstance(sources, list) else 0
        return base
    if category == "wiki":
        base["bucket"] = doc.bucket or ""
        return base
    if category == "writing":
        derived = fm.get("derived_from") or []
        base["derived_count"] = len(derived) if isinstance(derived, list) else 0
        return base
    raise ValueError(f"unknown category: {category}")


def build_list_page(out: Path, ctx: DashboardContext, category: str) -> Path:
    """Render `<category>.html` into `out` and return the written path.

    Raises ``ValueError`` for an unknown category.
    """
    if category not in _CATEGORIES:
        raise ValueError(f"unknown category: {category}")

    docs = list(ctx.registry.docs_by_category.get(category, []))
    columns = _columns_for(category)
    rows = [_row_for(d, category) for d in docs]
    statuses = sorted({r["status"] for r in rows if r.get("status")})

    html = render(
        "list.html.j2",
        title=category,
        depth=0,
        category=category,
        columns=columns,
        rows=rows,
        statuses=statuses,
    )
    target = out / f"{category}.html"
    target.write_text(html, encoding="utf-8")
    return target
