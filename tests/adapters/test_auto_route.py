from __future__ import annotations

import pytest

from pkm.adapters import auto_route


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://m.youtube.com/watch?v=abc", "youtube"),
        ("https://arxiv.org/abs/2310.06770", "openalex"),
        ("https://doi.org/10.1145/3597503.3623316", "openalex"),
        ("https://www.semanticscholar.org/paper/abc", "openalex"),
        ("https://martinfowler.com/articles/x.html", "jina"),
        ("https://example.com/", "jina"),
        ("https://news.ycombinator.com/item?id=1", "jina"),
    ],
)
def test_auto_route(url, expected):
    assert auto_route(url) == expected
