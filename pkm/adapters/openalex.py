"""OpenAlex adapter — academic URLs/DOIs → structured markdown.

Resolves arxiv IDs, DOIs, and OpenAlex IDs against the OpenAlex `works`
API (no key needed, polite-pool UA). Emits a markdown page with title,
authors, venue, abstract, top references, and top recent citations.

OpenAlex stores abstracts as `abstract_inverted_index` (term → positions)
to comply with publisher restrictions — we reconstruct the text locally.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from pkm.errors import PKMError


class OpenAlexError(PKMError):
    code = "OPENALEX_ERROR"


_WORKS = "https://api.openalex.org/works/"
_HEADERS = {
    "User-Agent": "pkm-adapters/0.1 (mailto:hwijung-park@linecorp.com)",
    "Accept": "application/json",
}
_TIMEOUT = 20.0

_ARXIV_BARE_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.I)
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_OPENALEX_ID_RE = re.compile(r"W\d{6,}", re.I)


def fetch(identifier: str, *, client=None) -> str:
    """Return a markdown page for a paper given any of: URL, DOI, arXiv ID, W-id."""
    import httpx  # lazy

    ident = _normalize(identifier)
    owns = client is None
    if owns:
        client = httpx.Client(timeout=_TIMEOUT, follow_redirects=True)
    try:
        try:
            resp = client.get(_WORKS + ident, headers=_HEADERS)
        except httpx.HTTPError as e:
            raise OpenAlexError(f"openalex fetch failed: {e}") from e
        if resp.status_code == 404:
            raise OpenAlexError(f"openalex: no work found for {identifier!r}")
        if resp.status_code != 200:
            raise OpenAlexError(f"openalex HTTP {resp.status_code}")
        work = resp.json() or {}
        refs = _fetch_short_works(client, work.get("referenced_works") or [], n=10)
        cited = _fetch_cited_by(client, work.get("id") or "", n=10)
    finally:
        if owns:
            client.close()

    return _render(work, refs, cited)


def _normalize(identifier: str) -> str:
    """Turn URL / DOI / arXiv id into the path OpenAlex accepts after /works/.

    Resolution order: OpenAlex W-id → arXiv (URL or bare NNNN.NNNNN[vN]) →
    DOI (URL or bare 10.xxxx/...). Order matters because a DOI regex would
    otherwise miss bare arXiv IDs (no slash) and W-ids look like neither.
    """
    s = identifier.strip()
    parsed = urlparse(s) if "://" in s else None
    host = (parsed.hostname or "").lower() if parsed else ""

    # OpenAlex W-id (URL or bare)
    m = _OPENALEX_ID_RE.search(s)
    if m and ("openalex" in host or "://" not in s):
        return m.group(0).upper()

    # arXiv: URL on arxiv.org OR bare "NNNN.NNNNN" pattern
    if "arxiv.org" in host:
        am = _ARXIV_RE.search(parsed.path if parsed else s)
        if am:
            return f"doi:10.48550/arXiv.{am.group(1)}"
    if _ARXIV_BARE_RE.match(s):
        return f"doi:10.48550/arXiv.{_ARXIV_BARE_RE.match(s).group(0).split('v')[0]}"

    # DOI URL or bare DOI
    if "doi.org" in host and parsed:
        path = parsed.path.lstrip("/")
        if _DOI_RE.match(path):
            return f"doi:{path}"
    m = _DOI_RE.search(s)
    if m:
        return f"doi:{m.group(0)}"

    raise OpenAlexError(
        f"could not extract DOI/arXiv/openalex id from {identifier!r}",
        hint="Pass a URL like https://arxiv.org/abs/2310.06770, a DOI, or an OpenAlex W-id.",
    )


def _fetch_short_works(client, work_ids: list[str], *, n: int) -> list[dict]:
    """Fetch up to `n` works in one filter query — used for references."""
    if not work_ids:
        return []
    import httpx

    short_ids = [w.rsplit("/", 1)[-1] for w in work_ids[:n]]
    try:
        resp = client.get(
            "https://api.openalex.org/works",
            params={
                "filter": "openalex_id:" + "|".join(short_ids),
                "per-page": str(n),
                "select": "id,title,publication_year,doi",
            },
            headers=_HEADERS,
        )
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []
    return ((resp.json() or {}).get("results") or [])[:n]


def _fetch_cited_by(client, work_url: str, *, n: int) -> list[dict]:
    if not work_url:
        return []
    import httpx

    work_id = work_url.rsplit("/", 1)[-1]
    try:
        resp = client.get(
            "https://api.openalex.org/works",
            params={
                "filter": f"cites:{work_id}",
                "per-page": str(n),
                "sort": "publication_date:desc",
                "select": "id,title,publication_year,doi",
            },
            headers=_HEADERS,
        )
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []
    return ((resp.json() or {}).get("results") or [])[:n]


def _reconstruct_abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}. Rebuild the prose."""
    if not isinstance(inverted, dict) or not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in inverted.items():
        if not isinstance(pos_list, list):
            continue
        for p in pos_list:
            if isinstance(p, int):
                positions.append((p, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def _format_authors(authorships: list[dict] | None) -> str:
    if not authorships:
        return "?"
    names: list[str] = []
    for a in authorships[:8]:
        author = a.get("author") or {}
        nm = author.get("display_name")
        if nm:
            names.append(nm)
    if len(authorships) > 8:
        names.append("et al.")
    return ", ".join(names) if names else "?"


def _render(work: dict, refs: list[dict], cited: list[dict]) -> str:
    title = (work.get("title") or work.get("display_name") or "(no title)").strip()
    authors = _format_authors(work.get("authorships"))
    year = work.get("publication_year") or "?"
    host = (work.get("host_venue") or work.get("primary_location") or {}).get("source") or {}
    venue = host.get("display_name") if isinstance(host, dict) else None
    if not venue:
        # fallback for some response shapes
        ploc = work.get("primary_location") or {}
        venue = (ploc.get("source") or {}).get("display_name") or "?"
    doi = (work.get("doi") or "").replace("https://doi.org/", "")
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

    parts = [f"# {title}", "", f"> {authors}. {venue}, {year}."]
    if doi:
        parts[-1] += f" DOI: {doi}"
    parts.append("")
    if abstract:
        parts += ["## Abstract", "", abstract, ""]
    if refs:
        parts += ["## References (top 10)", ""]
        for r in refs:
            t = (r.get("title") or "").strip() or "(no title)"
            y = r.get("publication_year") or "?"
            d = (r.get("doi") or "").replace("https://doi.org/", "")
            line = f"- {t} ({y})"
            if d:
                line += f" — DOI: {d}"
            parts.append(line)
        parts.append("")
    if cited:
        parts += ["## Cited by (recent)", ""]
        for c in cited:
            t = (c.get("title") or "").strip() or "(no title)"
            y = c.get("publication_year") or "?"
            d = (c.get("doi") or "").replace("https://doi.org/", "")
            line = f"- {t} ({y})"
            if d:
                line += f" — DOI: {d}"
            parts.append(line)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
