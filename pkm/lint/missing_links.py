"""Find semantically-close wiki pairs that aren't directly linked.

Used by:
- `pkm/lint/rules.py::_missing_link_candidate` (lint warning)
- `pkm/dashboard/pages/index.py` (Suggested links section)

Reads `.pkm/index.db`. If the DB is missing, sqlite-vec is unavailable, no wiki
embeddings exist, or the feature is disabled in config, returns []. Never
raises on data-shape problems — the lint and dashboard surfaces both treat
missing data as "feature unavailable, no findings".

Algorithm
---------
1. Load every wiki doc with a docs_vec embedding (excluding deprecated).
2. Build undirected adjacency from `links` table (`wikilink` + `derived_from`).
3. For each source doc, KNN top-K candidates from `docs_vec`.
4. Drop candidates where graph distance < `min_graph_distance`
   (`min_graph_distance=2` excludes directly-linked pairs).
5. Drop candidates with cosine similarity < `sim_threshold`.
6. Canonicalize each pair (sorted by path) and dedupe.
7. Cap per-source results at `top_k_per_doc`.

Configuration via `[lint.missing_link]` in `.pkm/config.toml`. See `_DEFAULTS`.

Distance metric note
--------------------
sqlite-vec's vec0 returns L2 (Euclidean) distance by default. Embeddings in
this project are L2-normalized (see `pkm.store.embedder`), so for unit vectors
the relationship is:

    L2 = sqrt(2 - 2 * cos_sim)
    cos_sim = 1 - L2**2 / 2

We expose a cosine-similarity threshold to the user (intuitive scale), and
convert internally to the L2 distance bound used by the KNN query.
"""

from __future__ import annotations

import math
import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "sim_threshold": 0.78,
    "min_graph_distance": 2,
    "top_k_per_doc": 3,
}

_LINK_KINDS = ("wikilink", "derived_from")
_INCLUDED_STATUSES = (None, "active", "stub")


@dataclass(frozen=True)
class LinkSuggestion:
    """A pair of wiki paths that look semantically close but aren't linked."""

    src_path: str  # canonical first (alphabetically smaller)
    dst_path: str
    similarity: float


def load_config(root: Path) -> dict[str, Any]:
    """Read `[lint.missing_link]` from `.pkm/config.toml`, applying defaults.

    Missing file or malformed TOML → defaults.
    """
    cfg_path = root / ".pkm" / "config.toml"
    out = dict(_DEFAULTS)
    if not cfg_path.exists():
        return out
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return out
    section = (data.get("lint") or {}).get("missing_link") or {}
    for key in _DEFAULTS:
        if key in section:
            out[key] = section[key]
    return out


def find_suggestions(root: Path) -> list[LinkSuggestion]:
    """Return suggested missing-link pairs, sorted by similarity desc.

    Returns [] silently if disabled, the DB is missing, sqlite-vec can't load,
    or the wiki has fewer than 2 embedded docs. Callers don't need to
    distinguish these cases.
    """
    cfg = load_config(root)
    if not cfg.get("enabled"):
        return []
    db_path = root / ".pkm" / "index.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        import sqlite_vec  # lazy — keeps `pkm lint` cheap when unused

        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, ImportError):
        conn.close()
        return []

    try:
        return _find_suggestions(conn, cfg)
    except sqlite3.OperationalError:
        # docs_vec / links may not exist yet (uninitialized index) — treat as empty.
        return []
    finally:
        conn.close()


def find_suggestions_for(
    root: Path,
    slug: str,
    *,
    n: int | None = None,
    threshold: float | None = None,
) -> list[LinkSuggestion]:
    """Suggestions for a single wiki slug. Filters the global pair list to
    those involving `slug` (canonical orientation: pair is reported either way).

    `n` overrides `top_k_per_doc` (cap on returned items).
    `threshold` overrides `sim_threshold` (cosine similarity floor).

    Returns [] when the slug is unknown, the index is missing, or the feature
    is disabled — never raises (consistent with `find_suggestions`).
    """
    cfg = load_config(root)
    if threshold is not None:
        cfg = {**cfg, "sim_threshold": float(threshold)}
    if n is not None:
        cfg = {**cfg, "top_k_per_doc": max(1, int(n))}
    if not cfg.get("enabled"):
        return []
    db_path = root / ".pkm" / "index.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, ImportError):
        conn.close()
        return []

    try:
        all_pairs = _find_suggestions(conn, cfg)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    target = f"/{slug}.md"
    matches = [s for s in all_pairs if s.src_path.endswith(target) or s.dst_path.endswith(target)]
    cap = int(cfg["top_k_per_doc"])
    return matches[:cap]


def _find_suggestions(conn: sqlite3.Connection, cfg: dict[str, Any]) -> list[LinkSuggestion]:
    sim_th = float(cfg["sim_threshold"])
    min_d = int(cfg["min_graph_distance"])
    top_k = max(1, int(cfg["top_k_per_doc"]))
    # vec0 returns L2 distance for unit vectors; convert the cosine threshold.
    # cos_sim = 1 - L2**2 / 2  →  L2 = sqrt(2 - 2*cos_sim)
    dist_max = math.sqrt(max(0.0, 2.0 - 2.0 * sim_th))

    # 1) Wiki docs with embeddings, excluding deprecated.
    rows = conn.execute(
        """
        SELECT d.id AS id, d.path AS path, d.status AS status
        FROM documents d
        JOIN docs_vec v ON v.doc_id = d.id
        WHERE d.bucket = 'wiki'
        ORDER BY d.id
        """
    ).fetchall()
    valid = [(r["id"], r["path"]) for r in rows if r["status"] in _INCLUDED_STATUSES]
    if len(valid) < 2:
        return []
    valid_ids = {i for i, _ in valid}
    path_by_id = {i: p for i, p in valid}

    # 2) Undirected adjacency (wikilink + derived_from).
    adj: dict[int, set[int]] = {i: set() for i in valid_ids}
    placeholders = ",".join("?" for _ in _LINK_KINDS)
    link_rows = conn.execute(
        f"SELECT src_doc_id, dst_doc_id FROM links "
        f"WHERE dst_doc_id IS NOT NULL AND kind IN ({placeholders})",
        _LINK_KINDS,
    ).fetchall()
    for r in link_rows:
        s, d = r["src_doc_id"], r["dst_doc_id"]
        if s in adj and d in adj and s != d:
            adj[s].add(d)
            adj[d].add(s)

    too_close_depth = max(0, min_d - 1)

    # 3-7) Iterate sources, KNN, filter, dedupe.
    seen_pairs: set[tuple[str, str]] = set()
    suggestions: list[LinkSuggestion] = []
    over = max(top_k * 4, 20)
    for doc_id, src_path in valid:
        emb_row = conn.execute(
            "SELECT embedding FROM docs_vec WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if not emb_row:
            continue
        cand_rows = conn.execute(
            f"""
            SELECT doc_id, distance FROM docs_vec
            WHERE embedding MATCH ?
            ORDER BY distance ASC
            LIMIT {over}
            """,
            (emb_row["embedding"],),
        ).fetchall()
        too_close = _reachable_within(adj, doc_id, too_close_depth)
        kept = 0
        for cand in cand_rows:
            if kept >= top_k:
                break
            cid = cand["doc_id"]
            if cid == doc_id or cid not in valid_ids or cid in too_close:
                continue
            dist = float(cand["distance"])
            if dist > dist_max:
                # KNN is sorted ascending; once we cross the threshold, stop.
                break
            cand_path = path_by_id[cid]
            a, b = (src_path, cand_path) if src_path < cand_path else (cand_path, src_path)
            if (a, b) in seen_pairs:
                kept += 1
                continue
            seen_pairs.add((a, b))
            cos_sim = 1.0 - (dist * dist) / 2.0
            suggestions.append(
                LinkSuggestion(src_path=a, dst_path=b, similarity=round(cos_sim, 4))
            )
            kept += 1

    suggestions.sort(key=lambda s: (-s.similarity, s.src_path, s.dst_path))
    return suggestions


def _reachable_within(adj: dict[int, set[int]], start: int, depth: int) -> set[int]:
    """Set of nodes reachable from `start` within `depth` hops (inclusive of start)."""
    seen = {start}
    if depth <= 0:
        return seen
    frontier = {start}
    for _ in range(depth):
        nxt: set[int] = set()
        for u in frontier:
            nxt |= adj.get(u, set())
        nxt -= seen
        if not nxt:
            break
        seen |= nxt
        frontier = nxt
    return seen
