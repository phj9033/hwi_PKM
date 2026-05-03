"""Build a single doc page (wiki or writing) at ``out/<doc.url_path>``.

Contract:

- ``build_doc_page(out, ctx, doc) -> Path`` writes the rendered HTML and
  returns the written path. Parent dirs are created.
- Only ``wiki`` and ``writing`` docs have ``url_path`` set; other categories
  are rejected with ``ValueError``.

Page sections (consumed by ``doc.html.j2``):

1. **Header** — title, status, lang, tags.
2. **Body** — ``render_markdown(doc.body, registry, depth=...)``. Depth is
   3 for wiki (``doc/wiki/<bucket>/<slug>.html``) and 2 for writing
   (``doc/writing/<slug>.html``).
3. **Aside** — frontmatter table (secret-masked), backlinks, outgoing,
   semantic neighbors, provenance.

All registry maps (``outgoing`` / ``backlinks`` / ``semantic``) are keyed by
``rel_path``. Targets that don't have a ``url_path`` (i.e. captures/chunks)
render as plain text — the link graph filter in scanner already drops them
for wiki/writing-only fields, but provenance reaches into ``raw/captures``.

Spec reference: M6 plan, Task 7.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pkm.dashboard._secrets import mask
from pkm.dashboard.context import DashboardContext
from pkm.dashboard.renderer import render_markdown
from pkm.dashboard.scanner import Doc, DocRegistry, Neighbor
from pkm.dashboard.templates import render

_REINDEX_HINT = "(index missing — run pkm reindex db)"


def _depth_for(doc: Doc) -> int:
    """Depth = number of `..` segments from the page back to dashboard root."""
    if doc.category == "wiki":
        return 3
    if doc.category == "writing":
        return 2
    raise ValueError(f"doc page only supported for wiki/writing, got {doc.category!r}")


def _link(prefix: str, target: Doc) -> dict[str, Any]:
    """Build a render-ready link dict for a target doc."""
    return {
        "title": target.title,
        "rel_path": target.rel_path,
        "href": prefix + target.url_path if target.url_path else "",
    }


def _link_list(rels: list[str], registry: DocRegistry, prefix: str) -> list[dict[str, Any]]:
    """Map a list of rel_paths to render-ready link dicts.

    Targets without a ``url_path`` (captures/chunks) are still represented but
    with ``href=""`` so the template can fall back to plain text.
    """
    out: list[dict[str, Any]] = []
    for rel in rels:
        target = registry.by_rel_path.get(rel)
        if target is None:
            out.append({"title": rel, "rel_path": rel, "href": ""})
            continue
        out.append(_link(prefix, target))
    return out


def _semantic_links(
    neighbors: list[Neighbor], registry: DocRegistry, prefix: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in neighbors:
        target = registry.by_rel_path.get(n.rel_path)
        href = prefix + target.url_path if target and target.url_path else ""
        out.append(
            {
                "title": n.title,
                "rel_path": n.rel_path,
                "score": round(n.score, 3),
                "href": href,
            }
        )
    return out


def _provenance_for(doc: Doc, registry: DocRegistry, prefix: str) -> dict[str, Any]:
    """Compute provenance section for the sidebar.

    - wiki + ``promoted_from``: a single source path string (typically a
      capture); rendered as plain text since captures don't have doc pages.
    - writing + ``derived_from``: list of slugs or paths; each item is linked
      to the corresponding wiki/writing doc page when resolvable, else plain.
    """
    fm = doc.frontmatter or {}
    if doc.category == "wiki":
        src = fm.get("promoted_from")
        if isinstance(src, str) and src:
            return {"kind": "promoted_from", "entries": [{"text": src, "href": ""}]}
        return {"kind": "promoted_from", "entries": []}

    # writing
    derived = fm.get("derived_from") or []
    if not isinstance(derived, list):
        return {"kind": "derived_from", "entries": []}

    entries: list[dict[str, str]] = []
    for entry in derived:
        if not isinstance(entry, str) or not entry:
            continue
        target = (
            registry.by_slug.get(entry)
            or registry.by_rel_path.get(entry)
            or registry.by_rel_path.get(_strip_data_prefix(entry))
        )
        if target and target.url_path:
            entries.append({"text": target.title, "href": prefix + target.url_path})
        else:
            entries.append({"text": entry, "href": ""})
    return {"kind": "derived_from", "entries": entries}


def _strip_data_prefix(path: str) -> str:
    return path[len("data/") :] if path.startswith("data/") else path


def _frontmatter_rows(doc: Doc) -> list[tuple[str, Any]]:
    """Flat (key, value) rows for the sidebar — masked for secret-shaped keys."""
    fm = doc.frontmatter or {}
    masked = mask(fm)
    return list(masked.items())


def build_doc_page(out: Path, ctx: DashboardContext, doc: Doc) -> Path:
    """Render ``out/<doc.url_path>`` and return the written path.

    Raises ``ValueError`` if ``doc.category`` is not ``wiki`` or ``writing``.
    """
    depth = _depth_for(doc)
    prefix = "../" * depth
    registry = ctx.registry

    body_html = render_markdown(doc.body, registry, depth=depth)

    backlinks = _link_list(registry.backlinks.get(doc.rel_path, []), registry, prefix)
    outgoing = _link_list(registry.outgoing.get(doc.rel_path, []), registry, prefix)

    db_path = ctx.root / ".pkm" / "index.db"
    db_present = db_path.exists()
    semantic = _semantic_links(registry.semantic.get(doc.rel_path, []), registry, prefix)

    provenance = _provenance_for(doc, registry, prefix)

    html = render(
        "doc.html.j2",
        title=doc.title,
        depth=depth,
        doc=doc,
        body_html=body_html,
        frontmatter_rows=_frontmatter_rows(doc),
        backlinks=backlinks,
        outgoing=outgoing,
        semantic=semantic,
        db_present=db_present,
        reindex_hint=_REINDEX_HINT,
        provenance=provenance,
    )

    target = out / doc.url_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target
