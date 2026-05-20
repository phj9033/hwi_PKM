from __future__ import annotations

import json

import httpx
import pytest

from pkm.adapters.reddit import RedditError, discussions


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_discussions_empty_when_no_submissions():
    captured = {}

    def handler(req):
        captured["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, text=json.dumps({"data": {"children": []}}))

    assert discussions("https://example.com/", client=_client(handler)) == ""
    assert captured["ua"] and "pkm-adapters" in captured["ua"]


def test_discussions_orders_by_score_desc_and_renders():
    def handler(req):
        return httpx.Response(
            200,
            text=json.dumps(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "subreddit": "programming",
                                    "score": 50,
                                    "num_comments": 10,
                                    "title": "low",
                                    "permalink": "/r/programming/comments/aaa/",
                                }
                            },
                            {
                                "data": {
                                    "subreddit": "rust",
                                    "score": 300,
                                    "num_comments": 80,
                                    "title": "HIGH",
                                    "permalink": "/r/rust/comments/bbb/",
                                }
                            },
                        ]
                    }
                }
            ),
        )

    md = discussions("https://example.com/", client=_client(handler))
    assert md.startswith("## Discussion — Reddit")
    # HIGH (score 300) must appear before low (score 50)
    assert md.index("HIGH") < md.index("low")
    assert "r/rust · 300 upvotes · 80 comments" in md
    assert "https://www.reddit.com/r/rust/comments/bbb/" in md


def test_discussions_silently_empty_on_429():
    def handler(req):
        return httpx.Response(429)

    assert discussions("https://example.com/", client=_client(handler)) == ""


def test_discussions_raises_on_other_http_errors():
    def handler(req):
        return httpx.Response(500)

    with pytest.raises(RedditError):
        discussions("https://example.com/", client=_client(handler))
