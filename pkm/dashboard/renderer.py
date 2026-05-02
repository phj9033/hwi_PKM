"""Markdown rendering with server-side wikilink resolution.

Spec reference: M6.3 plan. Wikilinks are resolved before markdown.markdown()
runs so the standard library passes the resulting raw HTML through unchanged.
"""

from __future__ import annotations

import re

import markdown as _markdown

from pkm.dashboard.scanner import DocRegistry

_MD_EXTENSIONS = ("fenced_code", "tables", "toc", "footnotes")
_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def render_markdown(body: str, registry: DocRegistry, *, depth: int) -> str:
    body = _resolve_wikilinks(body, registry, depth=depth)
    return _markdown.markdown(body, extensions=list(_MD_EXTENSIONS))


def _resolve_wikilinks(body: str, registry: DocRegistry, *, depth: int) -> str:
    prefix = "../" * depth

    def _sub(m: re.Match[str]) -> str:
        ref = m.group(1).strip()
        doc = (
            registry.by_slug.get(ref)
            or registry.by_rel_path.get(ref)
            or registry.by_rel_path.get(ref + ".md")
        )
        if doc is None or not doc.url_path:
            return f'<span class="wikilink-broken">{_escape(ref)}</span>'
        href = prefix + doc.url_path
        return f'<a class="wikilink" href="{_escape(href)}">{_escape(doc.title)}</a>'

    return _WIKILINK_RE.sub(_sub, body)


def make_snippet(body: str, *, max_chars: int = 200) -> str:
    s = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    s = re.sub(r"^#+\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*+([^*]+)\*+", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= max_chars else s[: max_chars - 1].rstrip() + "…"


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
