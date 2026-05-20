"""Jina Reader fallback — `r.jina.ai/<url>` → clean markdown.

Free, keyless. Renders JS and strips boilerplate. Used as the default
fallback when WebFetch returns thin/empty content for a non-specialized
URL. Single GET with one retry on transient failure.
"""

from __future__ import annotations

from pkm.errors import PKMError


class JinaError(PKMError):
    code = "JINA_ERROR"


_ENDPOINT = "https://r.jina.ai/"
_DEFAULT_TIMEOUT = 20.0


def fetch_markdown(url: str, *, timeout: float = _DEFAULT_TIMEOUT, client=None) -> str:
    """Fetch `url` through Jina Reader and return its markdown body.

    `client` is an injectable httpx.Client (used by tests). Production
    callers leave it None and we build a default client.
    """
    if not url.startswith(("http://", "https://")):
        raise JinaError(f"jina adapter requires http(s) URL, got {url!r}")
    import httpx  # lazy: keeps `pkm --help` sub-second when extras not installed

    target = _ENDPOINT + url
    headers = {
        "Accept": "text/markdown, text/plain;q=0.9, */*;q=0.1",
        "User-Agent": "pkm-adapters/0.1 (+https://github.com/phj9033/hwi_PKM)",
    }

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        last_exc: Exception | None = None
        for _ in range(2):  # one retry on transient failure
            try:
                resp = client.get(target, headers=headers)
                if resp.status_code == 200:
                    return resp.text.strip()
                if 500 <= resp.status_code < 600 or resp.status_code == 429:
                    last_exc = JinaError(f"jina HTTP {resp.status_code}")
                    continue
                raise JinaError(f"jina HTTP {resp.status_code} for {url}")
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                continue
        raise JinaError(f"jina failed after retry for {url}: {last_exc}") from last_exc
    finally:
        if owns_client:
            client.close()
