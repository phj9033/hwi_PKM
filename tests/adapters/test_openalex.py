from __future__ import annotations

import json

import httpx
import pytest

from pkm.adapters.openalex import OpenAlexError, _normalize, fetch


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://arxiv.org/abs/2310.06770", "doi:10.48550/arXiv.2310.06770"),
        ("https://arxiv.org/abs/2310.06770v2", "doi:10.48550/arXiv.2310.06770"),
        ("2310.06770", "doi:10.48550/arXiv.2310.06770"),
        ("https://doi.org/10.1145/3597503.3623316", "doi:10.1145/3597503.3623316"),
        ("10.1145/3597503.3623316", "doi:10.1145/3597503.3623316"),
        ("https://openalex.org/W4387123456", "W4387123456"),
    ],
)
def test_normalize(raw, expected):
    assert _normalize(raw) == expected


def test_normalize_rejects_unknown():
    with pytest.raises(OpenAlexError):
        _normalize("https://example.com/random-blog-post")


def _work_fixture() -> dict:
    return {
        "id": "https://openalex.org/W1111",
        "title": "SWE-bench",
        "publication_year": 2024,
        "doi": "https://doi.org/10.48550/arXiv.2310.06770",
        "primary_location": {"source": {"display_name": "ICLR"}},
        "authorships": [
            {"author": {"display_name": "Carlos E. Jimenez"}},
            {"author": {"display_name": "John Yang"}},
        ],
        "referenced_works": [
            "https://openalex.org/W2001",
            "https://openalex.org/W2002",
        ],
        "abstract_inverted_index": {
            "Language": [0],
            "models": [1],
            "have": [2],
            "made": [3],
            "progress.": [4],
        },
    }


def test_fetch_renders_full_markdown():
    def handler(req):
        url = str(req.url)
        if url.startswith("https://api.openalex.org/works/doi:"):
            return httpx.Response(200, text=json.dumps(_work_fixture()))
        if "filter=openalex_id" in url:
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "results": [
                            {"id": "W2001", "title": "HumanEval", "publication_year": 2021, "doi": ""},
                            {"id": "W2002", "title": "MBPP", "publication_year": 2021, "doi": ""},
                        ]
                    }
                ),
            )
        if "filter=cites%3A" in url or "filter=cites:" in url:
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "results": [
                            {"id": "W3001", "title": "AgentBench", "publication_year": 2024, "doi": ""},
                        ]
                    }
                ),
            )
        return httpx.Response(404)

    md = fetch("https://arxiv.org/abs/2310.06770", client=_client(handler))
    assert md.startswith("# SWE-bench")
    assert "Carlos E. Jimenez, John Yang" in md
    assert "ICLR, 2024" in md
    assert "DOI: 10.48550/arXiv.2310.06770" in md
    assert "## Abstract" in md
    assert "Language models have made progress." in md
    assert "## References (top 10)" in md
    assert "HumanEval (2021)" in md
    assert "## Cited by (recent)" in md
    assert "AgentBench (2024)" in md


def test_fetch_raises_on_404():
    def handler(req):
        return httpx.Response(404)

    with pytest.raises(OpenAlexError):
        fetch("10.1234/missing", client=_client(handler))


def test_fetch_handles_work_without_refs_or_citations():
    minimal = {
        "id": "https://openalex.org/W1",
        "title": "Solo paper",
        "publication_year": 2020,
        "doi": "",
        "primary_location": {"source": {"display_name": "?"}},
        "authorships": [],
        "referenced_works": [],
    }

    def handler(req):
        if str(req.url).startswith("https://api.openalex.org/works/doi:"):
            return httpx.Response(200, text=json.dumps(minimal))
        # cited-by query — return empty
        return httpx.Response(200, text=json.dumps({"results": []}))

    md = fetch("10.1234/solo", client=_client(handler))
    assert "Solo paper" in md
    assert "## References" not in md
    assert "## Cited by" not in md
