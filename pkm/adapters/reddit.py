"""Reddit discussion attachment via the public `.json` endpoint.

Given a URL, query `/api/info.json?url=<url>` to find submissions that
link to it. Polite UA required — Reddit blocks blank/default UAs.
Returns empty string when no submissions are found.
"""

from __future__ import annotations

from pkm.errors import PKMError


class RedditError(PKMError):
    code = "REDDIT_ERROR"


_INFO = "https://www.reddit.com/api/info.json"
_HEADERS = {"User-Agent": "pkm-adapters/0.1 by phj9033 (+https://github.com/phj9033/hwi_PKM)"}
_TIMEOUT = 15.0


def discussions(url: str, *, top_n: int = 3, client=None) -> str:
    """Return a `## Discussion — Reddit` markdown section, or ''."""
    import httpx  # lazy

    owns = client is None
    if owns:
        client = httpx.Client(timeout=_TIMEOUT, follow_redirects=True)
    try:
        try:
            resp = client.get(_INFO, params={"url": url}, headers=_HEADERS)
        except httpx.HTTPError as e:
            raise RedditError(f"reddit fetch failed: {e}") from e
        if resp.status_code == 429:
            return ""  # rate-limited: skip silently rather than blow up the capture
        if resp.status_code != 200:
            raise RedditError(f"reddit HTTP {resp.status_code}")
        children = ((resp.json() or {}).get("data") or {}).get("children") or []
        if not children:
            return ""
        children.sort(key=lambda c: (c.get("data") or {}).get("score") or 0, reverse=True)
        lines = ["## Discussion — Reddit", ""]
        for c in children[:top_n]:
            d = c.get("data") or {}
            sub = d.get("subreddit") or "?"
            score = d.get("score") or 0
            n_comments = d.get("num_comments") or 0
            title = (d.get("title") or "(no title)").strip()
            permalink = d.get("permalink")
            link = f"https://www.reddit.com{permalink}" if permalink else url
            lines.append(f"- r/{sub} · {score} upvotes · {n_comments} comments — {title}")
            lines.append(f"  {link}")
        lines.append("")
        return "\n".join(lines)
    finally:
        if owns:
            client.close()
