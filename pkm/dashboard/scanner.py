"""Dashboard scanner — walk `data/`, build `DocRegistry` with link graph + neighbors.

`scan(root)` is a pure function that:

1. Walks `<root>/data/`, partitioning markdown files into 4 categories:
   captures, chunks, wiki, writing.
2. Parses frontmatter to populate per-doc metadata (slug, title, tags, ...).
3. If `<root>/.pkm/index.db` exists, joins the M3 `links` table to produce the
   wiki+writing link graph (outgoing / backlinks) and queries `docs_vec` for
   top-5 semantic neighbors per doc.
4. If the DB is missing or any DB query fails, returns empty graphs — never
   propagates the error (the dashboard should still build).

Path-format decision (verified empirically against `_index_one`):

- `documents.path` in M3 is `str(abs_path.relative_to(root))`, i.e. it includes
  the `data/` prefix (e.g. `data/wiki/concepts/foo.md`).
- The scanner's `Doc.rel_path` is POSIX-relative to `data/` — *no* prefix
  (e.g. `wiki/concepts/foo.md`). This is what dashboard pages want for URL
  generation and is consistent with the test assertions.
- When joining with the link helpers we strip the `data/` prefix from each
  path the helpers return, and (for `_doc_id` lookups) prepend it back.

Wikilink slug resolution:

Wikilinks in PKM use slugs (e.g. `[[token-rotation]]`), not paths. The reindex
command stores them in `links.dst_path` but `dst_doc_id` stays NULL because
the slug doesn't match `documents.path`. `pkm.search.related._outgoing` only
returns rows where `dst_doc_id` is set — so it misses slug-style wikilinks.
To populate the dashboard graph we additionally read raw `dst_path` strings
for unresolved wikilinks and resolve them through `registry.by_slug`. This
is one targeted query (per direction) and is the minimum needed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from pkm.search.related import _doc_id, _incoming, _outgoing, _semantic
from pkm.store.frontmatter import parse as parse_fm

_CATEGORIES: tuple[str, ...] = ("captures", "chunks", "wiki", "writing")


@dataclass(frozen=True)
class Doc:
    category: str
    bucket: str | None
    path: Path
    rel_path: str
    url_path: str
    slug: str | None
    title: str
    status: str | None
    lang: str | None
    tags: tuple[str, ...]
    frontmatter: dict
    body: str


@dataclass(frozen=True)
class Neighbor:
    rel_path: str
    title: str
    score: float


@dataclass
class DocRegistry:
    docs_by_category: dict[str, list[Doc]] = field(default_factory=dict)
    by_rel_path: dict[str, Doc] = field(default_factory=dict)
    by_slug: dict[str, Doc] = field(default_factory=dict)
    outgoing: dict[str, list[str]] = field(default_factory=dict)
    backlinks: dict[str, list[str]] = field(default_factory=dict)
    semantic: dict[str, list[Neighbor]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Walk + categorize
# --------------------------------------------------------------------------- #


def _categorize(rel_parts: tuple[str, ...]) -> tuple[str | None, str | None]:
    """Return (category, bucket) for a path under data/.

    rel_parts is the POSIX-split path relative to data/.
    """
    if len(rel_parts) >= 3 and rel_parts[0] == "raw" and rel_parts[1] == "captures":
        return "captures", None
    if len(rel_parts) >= 3 and rel_parts[0] == "raw" and rel_parts[1] == "chunks":
        return "chunks", None
    if len(rel_parts) >= 3 and rel_parts[0] == "wiki":
        return "wiki", rel_parts[1]
    if len(rel_parts) >= 2 and rel_parts[0] == "writing":
        return "writing", None
    return None, None


def _url_path(category: str, bucket: str | None, stem: str) -> str:
    if category == "wiki" and bucket:
        return f"doc/wiki/{bucket}/{stem}.html"
    if category == "writing":
        return f"doc/writing/{stem}.html"
    return ""


def _build_doc(category: str, bucket: str | None, abs_path: Path, data_root: Path) -> Doc:
    rel = abs_path.relative_to(data_root).as_posix()
    text = abs_path.read_text(encoding="utf-8")
    try:
        fm, body = parse_fm(text)
    except Exception:
        # A malformed frontmatter shouldn't kill the whole dashboard build.
        fm, body = {}, text

    raw_tags = fm.get("tags") or ()
    tags: tuple[str, ...] = tuple(t for t in raw_tags if isinstance(t, str))

    fm_slug = fm.get("slug")
    fm_title = fm.get("title")
    fm_status = fm.get("status")
    fm_lang = fm.get("lang")

    return Doc(
        category=category,
        bucket=bucket,
        path=abs_path,
        rel_path=rel,
        url_path=_url_path(category, bucket, abs_path.stem),
        slug=fm_slug if isinstance(fm_slug, str) else None,
        title=fm_title if isinstance(fm_title, str) else abs_path.stem,
        status=fm_status if isinstance(fm_status, str) else None,
        lang=fm_lang if isinstance(fm_lang, str) else None,
        tags=tags,
        frontmatter=fm,
        body=body,
    )


def _walk_data(data_root: Path) -> list[Doc]:
    docs: list[Doc] = []
    if not data_root.exists():
        return docs
    for abs_path in sorted(data_root.rglob("*.md")):
        if not abs_path.is_file():
            continue
        rel_parts = abs_path.relative_to(data_root).parts
        category, bucket = _categorize(rel_parts)
        if category is None:
            continue
        docs.append(_build_doc(category, bucket, abs_path, data_root))
    return docs


# --------------------------------------------------------------------------- #
# Link graph + semantic neighbors
# --------------------------------------------------------------------------- #


def _strip_data(path: str) -> str:
    """Convert a documents.path (with `data/` prefix) to registry rel_path form."""
    if path.startswith("data/"):
        return path[len("data/") :]
    return path


def _add_data(rel_path: str) -> str:
    return f"data/{rel_path}"


def _filter_to_linkable(rels: list[str], linkable: set[str]) -> list[str]:
    """Dedupe (preserving order) and keep only paths in the linkable set."""
    out: list[str] = []
    seen: set[str] = set()
    for r in rels:
        if r in linkable and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _slug_outgoing(db: sqlite3.Connection, doc_id: int, by_slug: dict[str, Doc]) -> list[str]:
    """Return rel_paths reached from this doc via slug-style wikilinks.

    Wikilinks are stored in `links.dst_path` as raw slugs (unresolved). We pull
    the unresolved rows for this src doc and map them through `by_slug` to
    rel_paths. This complements `_outgoing`, which only sees resolved links.
    """
    rows = db.execute(
        "SELECT dst_path FROM links "
        "WHERE src_doc_id = ? AND kind = 'wikilink' AND dst_doc_id IS NULL",
        (doc_id,),
    ).fetchall()
    out: list[str] = []
    for r in rows:
        slug = r[0]
        if slug and slug in by_slug:
            out.append(by_slug[slug].rel_path)
    return out


def _slug_incoming(
    db: sqlite3.Connection, doc_id: int, by_path_with_data: dict[str, Doc]
) -> list[str]:
    """Return rel_paths of docs whose slug-style wikilinks point at this doc.

    We resolve from the doc's slug (looked up via doc_id → documents.path → registry).
    """
    me = db.execute("SELECT path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not me:
        return []
    my_doc = by_path_with_data.get(me[0])
    if my_doc is None or my_doc.slug is None:
        return []
    rows = db.execute(
        "SELECT d1.path FROM links L JOIN documents d1 ON d1.id = L.src_doc_id "
        "WHERE L.dst_path = ? AND L.kind = 'wikilink' AND L.dst_doc_id IS NULL",
        (my_doc.slug,),
    ).fetchall()
    return [_strip_data(r[0]) for r in rows]


def _populate_graph_and_semantic(
    db: sqlite3.Connection,
    docs: list[Doc],
    by_rel_path: dict[str, Doc],
    by_slug: dict[str, Doc],
) -> tuple[dict, dict, dict]:
    """Walk wiki+writing docs, populate outgoing/backlinks/semantic dicts."""
    outgoing: dict[str, list[str]] = {}
    backlinks: dict[str, list[str]] = {}
    semantic: dict[str, list[Neighbor]] = {}

    linkable_rels = {d.rel_path for d in docs if d.category in ("wiki", "writing")}
    by_path_with_data = {_add_data(d.rel_path): d for d in docs}

    for d in docs:
        if d.category not in ("wiki", "writing"):
            continue
        doc_id = _doc_id(db, _add_data(d.rel_path))
        if doc_id is None:
            continue

        # Outgoing: resolved-path wikilinks + slug-resolved wikilinks.
        out_resolved = [_strip_data(p) for p in _outgoing(db, doc_id, "wikilink")]
        out_slug = _slug_outgoing(db, doc_id, by_slug)
        outgoing[d.rel_path] = _filter_to_linkable(out_resolved + out_slug, linkable_rels)

        # Incoming: resolved + slug-resolved.
        in_resolved = [_strip_data(p) for p in _incoming(db, doc_id, "wikilink")]
        in_slug = _slug_incoming(db, doc_id, by_path_with_data)
        backlinks[d.rel_path] = _filter_to_linkable(in_resolved + in_slug, linkable_rels)

        # Semantic neighbors: top-5, paths converted + filtered through registry.
        rows = _semantic(db, doc_id, 5)
        neighbors: list[Neighbor] = []
        for row in rows:
            n_path = _strip_data(row.get("path", ""))
            target = by_rel_path.get(n_path)
            if target is None:
                continue
            neighbors.append(
                Neighbor(
                    rel_path=n_path,
                    title=target.title,
                    score=float(row.get("similarity", 0.0)),
                )
            )
        semantic[d.rel_path] = neighbors

    return outgoing, backlinks, semantic


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #


def scan(root: Path) -> DocRegistry:
    """Walk `<root>/data/` and return a partitioned DocRegistry.

    See module docstring for the path-format and graph-population contract.
    """
    data_root = root / "data"
    docs = _walk_data(data_root)

    docs_by_category: dict[str, list[Doc]] = {c: [] for c in _CATEGORIES}
    by_rel_path: dict[str, Doc] = {}
    by_slug: dict[str, Doc] = {}
    for d in docs:
        docs_by_category[d.category].append(d)
        by_rel_path[d.rel_path] = d
        if d.slug and d.category in ("wiki", "writing"):
            by_slug[d.slug] = d

    outgoing: dict = {}
    backlinks: dict = {}
    semantic: dict = {}

    db_path = root / ".pkm" / "index.db"
    if db_path.exists():
        try:
            from pkm.store.index_db import connect

            db = connect(root)
            try:
                outgoing, backlinks, semantic = _populate_graph_and_semantic(
                    db, docs, by_rel_path, by_slug
                )
            finally:
                db.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError):
            outgoing, backlinks, semantic = {}, {}, {}

    return DocRegistry(
        docs_by_category=docs_by_category,
        by_rel_path=by_rel_path,
        by_slug=by_slug,
        outgoing=outgoing,
        backlinks=backlinks,
        semantic=semantic,
    )
