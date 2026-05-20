from __future__ import annotations

import json

import httpx
import pytest

from pkm.adapters.hn import HNError, discussions


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_discussions_empty_when_no_hits():
    def handler(req):
        assert "hn.algolia.com" in str(req.url)
        return httpx.Response(200, text=json.dumps({"hits": []}))

    assert discussions("https://example.com/", client=_client(handler)) == ""


def test_discussions_renders_top_hit_and_comment():
    def handler(req):
        url = str(req.url)
        if "/search" in url:
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "hits": [
                            {
                                "objectID": "111",
                                "title": "Cool article",
                                "points": 423,
                                "num_comments": 187,
                            }
                        ]
                    }
                ),
            )
        if "/items/111" in url:
            return httpx.Response(
                200,
                text=json.dumps(
                    {"children": [{"text": "<p>top <b>comment</b> body</p>"}]}
                ),
            )
        return httpx.Response(404)

    md = discussions("https://example.com/", client=_client(handler))
    assert "## Discussion — Hacker News" in md
    assert "423 points, 187 comments" in md
    assert "Cool article" in md
    assert "https://news.ycombinator.com/item?id=111" in md
    assert "> top comment body" in md


def test_discussions_raises_on_search_5xx():
    def handler(req):
        return httpx.Response(500)

    with pytest.raises(HNError):
        discussions("https://example.com/", client=_client(handler))
