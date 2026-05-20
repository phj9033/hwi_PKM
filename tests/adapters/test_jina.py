from __future__ import annotations

import httpx
import pytest

from pkm.adapters.jina import JinaError, fetch_markdown


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_markdown_happy_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, text="# Hello\n\nbody.")

    out = fetch_markdown("https://example.com/x", client=_client(handler))
    assert out == "# Hello\n\nbody."
    assert captured["url"] == "https://r.jina.ai/https://example.com/x"
    assert "pkm-adapters" in captured["ua"]


def test_fetch_markdown_retries_on_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="oops")
        return httpx.Response(200, text="recovered")

    assert fetch_markdown("https://example.com/", client=_client(handler)) == "recovered"
    assert calls["n"] == 2


def test_fetch_markdown_raises_after_persistent_5xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="oops")

    with pytest.raises(JinaError):
        fetch_markdown("https://example.com/", client=_client(handler))


def test_fetch_markdown_rejects_non_http_url():
    with pytest.raises(JinaError):
        fetch_markdown("ftp://example.com/", client=_client(lambda r: httpx.Response(200)))


def test_fetch_markdown_raises_on_non_retryable_4xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    with pytest.raises(JinaError):
        fetch_markdown("https://example.com/missing", client=_client(handler))
