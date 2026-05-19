"""`pkm reindex db` — build/refresh `.pkm/index.db` from disk.

Usage::

    pkm reindex db                                 # incremental (hash compare)
    pkm reindex db data/wiki/concepts/foo.md       # single file
    pkm reindex db --full                          # drop + rebuild everything
    pkm reindex db --scope wiki                    # filter by bucket
    pkm reindex db --low-memory                    # batch_size=4 for embedder

Master spec §3.2, §5.1 (scope policy), §5.6 (model mgmt).

This command IS itself the side-effect chokepoint for indexing. It does NOT
call `_post_mutation` (which would recurse into a reindex on every reindex).
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMConfigError, PKMError, PKMStateError
from pkm.store.chunker import split_markdown
from pkm.store.embedder import get_embedder
from pkm.store.frontmatter import parse as parse_fm
from pkm.store.index_db import connect

_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+?)\]\]")

# Bucket prefixes match master spec §2 layout.
_BUCKETS = {
    "wiki": "data/wiki",
    "captures": "data/raw/captures",
    "chunks": "data/raw/chunks",
    "writing": "data/writing",
    "style": "data/style",                                    # M8
    "projects": "data/projects",                              # M13
}
_SCOPE_BUCKETS = {
    "wiki": ("wiki",),
    "raw": ("captures", "chunks"),
    "writing": ("writing",),
    "style": ("style",),                                      # M8
    "projects": ("projects",),                                # M13
    "all": ("wiki", "captures", "chunks", "writing", "style", "projects"),  # M13: +projects
}


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(obj):
    """JSON serializer for types not handled by default (e.g. datetime from YAML)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _vec_opted_in(root: Path) -> bool:
    cfg = root / ".pkm" / "config.toml"
    if not cfg.exists():
        return False
    try:
        with cfg.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return False
    return bool(data.get("index", {}).get("vec_captures", False))


def _walk_files(root: Path, buckets: Iterable[str]) -> list[tuple[str, Path]]:
    """Yield (bucket_name, abs_path) for every .md file under each bucket."""
    out: list[tuple[str, Path]] = []
    for b in buckets:
        base = root / _BUCKETS[b]
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.is_file():
                out.append((b, p))
    return out


def _index_one(
    conn,
    root: Path,
    bucket: str,
    abs_path: Path,
    embedder,
    vec_opted_in: bool,
    *,
    post_m002: bool = False,
    post_m003: bool = False,
    tokenizer=None,
) -> bool:
    """Index a single file. Returns True if (re)indexed, False if skipped."""
    rel = str(abs_path.relative_to(root))
    text = abs_path.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    chash = _content_hash(body)

    existing = conn.execute(
        "SELECT id, content_hash FROM documents WHERE path = ?", (rel,)
    ).fetchone()
    if existing and existing["content_hash"] == chash:
        return False

    chunks = split_markdown(text)
    if not chunks:
        chunks = []  # empty docs allowed; document row still tracked

    # Upsert documents row (path UNIQUE → stable doc_id across reindex).
    conn.execute(
        """
        INSERT INTO documents(path, bucket, title, lang, status, source_url,
                              frontmatter_json, content_hash, indexed_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(path) DO UPDATE SET
          bucket=excluded.bucket, title=excluded.title, lang=excluded.lang,
          status=excluded.status, source_url=excluded.source_url,
          frontmatter_json=excluded.frontmatter_json,
          content_hash=excluded.content_hash, indexed_at=excluded.indexed_at
        """,
        (
            rel,
            bucket,
            fm.get("title"),
            fm.get("lang"),
            fm.get("status"),
            fm.get("source_url"),
            json.dumps(fm, ensure_ascii=False, default=_json_default) if fm else None,
            chash,
        ),
    )
    doc_id = conn.execute("SELECT id FROM documents WHERE path=?", (rel,)).fetchone()[0]

    # Wipe old chunks/fts/vec/links for this doc.
    # FTS5 + vec0 are virtual tables — they do NOT honor SQLite FK CASCADE.
    # Delete from them BEFORE chunks (otherwise we lose the chunk_id list).
    if not post_m002:
        # V1 contentless FTS5: rowid-targeted DELETE works.
        conn.execute(
            "DELETE FROM chunks_fts WHERE rowid IN "
            "(SELECT id FROM chunks WHERE doc_id = ?)",
            (doc_id,),
        )
    # Post-m002 (content=chunks FTS5): a single end-of-loop 'rebuild' in
    # reindex_db handles invalidation. Per-doc DELETE is unnecessary and the
    # contentless idiom doesn't apply.
    conn.execute(
        "DELETE FROM chunks_vec WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    # docs_vec.doc_id is PRIMARY KEY in a vec0 virtual table — no FK cascade
    # from documents, and the INSERT below would hit UNIQUE on re-index.
    conn.execute("DELETE FROM docs_vec WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM links WHERE src_doc_id = ?", (doc_id,))

    do_vector = (bucket in ("wiki", "style", "projects")) or (bucket in ("captures", "chunks") and vec_opted_in)
    embeddings = None
    if do_vector and chunks:
        embeddings = embedder.embed([c.text for c in chunks])

    for i, ch in enumerate(chunks):
        if post_m003:
            cur = conn.execute(
                """
                INSERT INTO chunks(doc_id, chunk_idx, heading_path, text, token_count,
                                   project, category, session_id)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    doc_id,
                    ch.chunk_idx,
                    json.dumps(ch.heading_path, ensure_ascii=False),
                    ch.text,
                    ch.token_count,
                    fm.get("project"),
                    fm.get("category"),
                    fm.get("session_id"),
                ),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO chunks(doc_id, chunk_idx, heading_path, text, token_count)
                VALUES (?,?,?,?,?)
                """,
                (
                    doc_id,
                    ch.chunk_idx,
                    json.dumps(ch.heading_path, ensure_ascii=False),
                    ch.text,
                    ch.token_count,
                ),
            )
        chunk_id = cur.lastrowid
        if post_m002:
            # Post-m002: write pre-tokenized text into chunks.text_tokenized.
            # No per-row chunks_fts INSERT — single 'rebuild' after the main
            # loop in reindex_db keeps it O(N).
            from pkm.search.tokenizer import tokenize_for_indexing

            tokenized = tokenize_for_indexing(
                ch.text, lang=fm.get("lang"), tokenizer=tokenizer
            )
            conn.execute(
                "UPDATE chunks SET text_tokenized = ? WHERE id = ?",
                (tokenized, chunk_id),
            )
        else:
            conn.execute(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                (chunk_id, ch.text),
            )
        if embeddings is not None:
            conn.execute(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embeddings[i].astype("float32").tobytes()),
            )

    # Insert doc-level embedding into docs_vec (mean-pool over chunk embeddings).
    if embeddings is not None and len(embeddings) > 0:
        import numpy as np

        doc_vec = embeddings.mean(axis=0).astype(np.float32)
        norm = np.linalg.norm(doc_vec)
        if norm > 0.0:
            doc_vec = doc_vec / norm
        conn.execute(
            "INSERT INTO docs_vec(doc_id, embedding) VALUES (?, ?)",
            (doc_id, doc_vec.tobytes()),
        )

    # Extract and insert links (wikilinks, derived_from, tags) from this doc.
    link_rows: list[tuple[int, None, str, str]] = []

    for m in _WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        link_rows.append((doc_id, None, target, "wikilink"))

    for ref in fm.get("derived_from") or []:
        if isinstance(ref, str):
            link_rows.append((doc_id, None, ref, "derived_from"))

    for tag in fm.get("tags") or []:
        if isinstance(tag, str):
            link_rows.append((doc_id, None, tag, "tag"))

    if link_rows:
        conn.executemany(
            "INSERT INTO links(src_doc_id, dst_doc_id, dst_path, kind) VALUES (?,?,?,?)",
            link_rows,
        )
        # Resolve dst_doc_id where dst_path matches documents.path exactly.
        # Bare slugs (e.g. "oauth-token-storage") stay unresolved (dst_doc_id NULL).
        # The BROKEN_WIKILINK lint rule surfaces unresolved wikilinks separately.
        conn.execute(
            """
            UPDATE links SET dst_doc_id = (
                SELECT id FROM documents WHERE documents.path = links.dst_path
            )
            WHERE src_doc_id = ? AND dst_doc_id IS NULL AND dst_path IS NOT NULL
            """,
            (doc_id,),
        )

    return True


def _drop_all(conn, *, post_m002: bool = False) -> None:
    """Wipe every indexable row.

    Virtual tables (chunks_fts, chunks_vec, docs_vec) do NOT honor SQLite FK
    cascade, so each gets explicit handling.

    Pre-m002 chunks_fts is a *contentless* FTS5 table (`content=''` in
    index_schema.py), which does NOT support row DELETE. The supported idiom
    is the special 'delete-all' command insert. See SQLite FTS5 docs §4.4.3.

    Post-m002 chunks_fts is a content-table form (`content=chunks`); the
    'delete-all' command is contentless-only. We rely on the end-of-loop
    'rebuild' in reindex_db to resync after chunks rows are repopulated.
    """
    if not post_m002:
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
    conn.execute("DELETE FROM chunks_vec")
    conn.execute("DELETE FROM docs_vec")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM links")
    conn.execute("DELETE FROM documents")


def _bucket_for(root: Path, abs_path: Path) -> str | None:
    try:
        rel = abs_path.relative_to(root)
    except ValueError:
        return None
    rel_str = str(rel)
    for name, prefix in _BUCKETS.items():
        if rel_str.startswith(prefix + "/") or rel_str == prefix:
            return name
    return None


def register(app: typer.Typer) -> None:
    reindex = typer.Typer(name="reindex", help="Search index management.")
    app.add_typer(reindex)

    @reindex.command("db")
    def reindex_db(
        path: Path | None = typer.Argument(
            None, help="Specific file/glob to reindex (overrides --scope)."
        ),
        full: bool = typer.Option(False, "--full", help="Drop everything and rebuild."),
        scope: str = typer.Option(
            "all",
            "--scope",
            help="Bucket filter: wiki | raw | writing | style | projects | all | project:<id>.",
        ),
        low_memory: bool = typer.Option(
            False, "--low-memory", help="Use batch_size=4 for embedder."
        ),
        root: Path | None = typer.Option(None, "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        if root is None:
            resolved = resolve_data_repo()
            if resolved is None:
                raise PKMConfigError(
                    "Cannot resolve data repo for reindex.",
                    hint="Pass -r <path>, set PKM_DATA_REPO, or run `pkm install`.",
                )
            root = resolved

        # Resolve project:<id> scope into an explicit file list.
        _project_id_scope: str | None = None
        if scope.startswith("project:"):
            _project_id_scope = scope[len("project:"):]
        elif scope not in _SCOPE_BUCKETS:
            raise PKMError(f"unknown scope: {scope!r}", hint=f"Choose from: {list(_SCOPE_BUCKETS)} or project:<id>")

        conn = connect(root)
        try:
            from pkm.search.tokenizer import detect_active, get_tokenizer

            active = detect_active(conn)
            post_m002 = active == "kiwi"
            tokenizer = get_tokenizer(active) if post_m002 else None

            # Detect m003 columns (project/category/session_id) — mirrors post_m002 idiom.
            chunks_columns = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
            post_m003 = "project" in chunks_columns

            if full:
                _drop_all(conn, post_m002=post_m002)

            embedder = get_embedder(low_memory=low_memory)
            vec_opt = _vec_opted_in(root)

            if path is not None:
                abs_path = path.resolve()
                bucket = _bucket_for(root.resolve(), abs_path)
                if bucket is None:
                    raise PKMStateError(
                        f"path {path} is not under any bucket",
                        hint=f"Allowed roots: {list(_BUCKETS.values())}",
                    )
                files = [(bucket, abs_path)]
            elif _project_id_scope is not None:
                # project:<id> — walk only data/projects/<id>/**/*.md
                project_dir = root.resolve() / "data" / "projects" / _project_id_scope
                if not project_dir.exists():
                    raise PKMStateError(
                        f"project directory not found: data/projects/{_project_id_scope}",
                        hint="Create the project with `pkm project link` first.",
                    )
                files = [
                    ("projects", p)
                    for p in sorted(project_dir.rglob("*.md"))
                    if p.is_file()
                ]
            else:
                files = _walk_files(root.resolve(), _SCOPE_BUCKETS[scope])

            indexed = 0
            skipped = 0
            for bucket, abs_p in files:
                if _index_one(
                    conn,
                    root.resolve(),
                    bucket,
                    abs_p,
                    embedder,
                    vec_opt,
                    post_m002=post_m002,
                    post_m003=post_m003,
                    tokenizer=tokenizer,
                ):
                    indexed += 1
                else:
                    skipped += 1

            # Post-m002: rebuild chunks_fts ONCE after the loop. Content-table
            # FTS5 doesn't auto-sync on chunks updates, and per-row 'rebuild'
            # would be O(N²).
            if post_m002:
                conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")

            conn.commit()

            stats = {
                "documents_indexed": indexed,
                "documents_skipped": skipped,
                "scope": scope,
                "full": full,
            }
            if json_out:
                typer.echo(json.dumps({"ok": True, "stats": stats}, ensure_ascii=False))
            else:
                typer.echo(
                    f"reindex db: {indexed} indexed, {skipped} skipped (scope={scope}, full={full})"
                )
        finally:
            conn.close()
