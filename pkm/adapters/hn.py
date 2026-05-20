"""Hacker News discussion attachment via Algolia search API.

Given a URL, find the highest-signal HN story discussing it and emit a
markdown section with title, points, comment count, and the top comment
snippet. Returns an empty string if there is no discussion — the slash
template just appends, so empty = no section.
"""

from __future__ import annotations

from pkm.errors import PKMError


class HNError(PKMError):
    code = "HN_ERROR"


_SEARCH = "https://hn.algolia.com/api/v1/search"
_ITEM = "https://hn.algolia.com/api/v1/items/"
_STORY = "https://news.ycombinator.com/item?id="
_HEADERS = {"User-Agent": "pkm-adapters/0.1 (+https://github.com/phj9033/hwi_PKM)"}
_TIMEOUT = 15.0


def discussions(url: str, *, top_n: int = 3, client=None) -> str:
    """Return a `## Discussion — Hacker News` markdown section, or ''."""
    import httpx  # lazy

    owns = client is None
    if owns:
        client = httpx.Client(timeout=_TIMEOUT, follow_redirects=True)
    try:
        try:
            resp = client.get(
                _SEARCH,
                params={"query": url, "tags": "story", "hitsPerPage": str(top_n)},
                headers=_HEADERS,
            )
        except httpx.HTTPError as e:
            raise HNError(f"HN search failed: {e}") from e
        if resp.status_code != 200:
            raise HNError(f"HN search HTTP {resp.status_code}")
        hits = (resp.json() or {}).get("hits") or []
        if not hits:
            return ""
        lines = ["## Discussion — Hacker News", ""]
        for hit in hits[:top_n]:
            title = hit.get("title") or hit.get("story_title") or "(no title)"
            points = hit.get("points") or 0
            n_comments = hit.get("num_comments") or 0
            obj_id = hit.get("objectID")
            link = f"{_STORY}{obj_id}" if obj_id else url
            lines.append(f"- [{points} points, {n_comments} comments] {title} — {link}")
            top_comment = _fetch_top_comment(client, obj_id) if obj_id else None
            if top_comment:
                snippet = _shorten(top_comment, 240)
                lines.append(f"  > {snippet}")
        lines.append("")
        return "\n".join(lines)
    finally:
        if owns:
            client.close()


def _fetch_top_comment(client, story_id: str) -> str | None:
    """Best-effort: pull the first non-empty child comment of a story."""
    import httpx

    try:
        resp = client.get(f"{_ITEM}{story_id}", headers=_HEADERS)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json() or {}
    for child in data.get("children") or []:
        text = (child.get("text") or "").strip()
        if text:
            return _strip_html(text)
    return None


def _strip_html(text: str) -> str:
    """Crude HTML → text. Algolia returns HTML in comment bodies."""
    import re

    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _shorten(s: str, limit: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"
