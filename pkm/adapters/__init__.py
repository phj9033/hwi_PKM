"""Network-aware adapters: URL → markdown.

This namespace is the *only* place inside `pkm/` that performs HTTP I/O.
Core mutations, store, search, lint, dashboard must stay network-free —
treat any `from pkm.adapters...` import outside `pkm/commands/adapter.py`
and `pkm/commands/enrich.py` as a regression.

Each adapter exposes a single function returning a markdown string and is
pure-ish: same input → same output (modulo upstream API drift).
"""

from __future__ import annotations

from urllib.parse import urlparse

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_OPENALEX_HOSTS = {
    "arxiv.org",
    "www.arxiv.org",
    "doi.org",
    "dx.doi.org",
    "openalex.org",
    "api.openalex.org",
    "semanticscholar.org",
    "www.semanticscholar.org",
}


def auto_route(url: str) -> str:
    """Pick the best adapter name for a URL based on its host.

    Returns one of: "youtube", "openalex", "jina". The default ("jina") is
    the safe generic fallback — any URL can be sent through Jina Reader.
    """
    host = (urlparse(url).hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        return "youtube"
    if host in _OPENALEX_HOSTS:
        return "openalex"
    return "jina"
