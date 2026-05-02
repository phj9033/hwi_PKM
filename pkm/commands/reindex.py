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
import tomllib
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import typer

from pkm.errors import PKMError, PKMStateError
from pkm.store.chunker import split_markdown
from pkm.store.embedder import get_embedder
from pkm.store.frontmatter import parse as parse_fm
from pkm.store.index_db import connect

# Bucket prefixes match master spec §2 layout.
_BUCKETS = {
    "wiki": "data/wiki",
    "captures": "data/raw/captures",
    "chunks": "data/raw/chunks",
    "writing": "data/writing",
}
_SCOPE_BUCKETS = {
    "wiki": ("wiki",),
    "raw": ("captures", "chunks"),
    "writing": ("writing",),
    "all": ("wiki", "captures", "chunks", "writing"),
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


def _index_one(conn, root: Path, bucket: str, abs_path: Path, embedder, vec_opted_in: bool) -> bool:
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
    conn.execute(
        "DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.execute(
        "DELETE FROM chunks_vec WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM links WHERE src_doc_id = ?", (doc_id,))

    do_vector = (bucket == "wiki") or (bucket in ("captures", "chunks") and vec_opted_in)
    embeddings = None
    if do_vector and chunks:
        embeddings = embedder.embed([c.text for c in chunks])

    for i, ch in enumerate(chunks):
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
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)", (chunk_id, ch.text))
        if embeddings is not None:
            conn.execute(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embeddings[i].astype("float32").tobytes()),
            )
    return True


def _drop_all(conn) -> None:
    """Wipe every indexable row.

    Virtual tables (chunks_fts, chunks_vec, docs_vec) do NOT honor SQLite FK
    cascade, so each gets an explicit DELETE.
    """
    conn.execute("DELETE FROM chunks_fts")
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
            "all", "--scope", help="Bucket filter: wiki | raw | writing | all."
        ),
        low_memory: bool = typer.Option(
            False, "--low-memory", help="Use batch_size=4 for embedder."
        ),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        if scope not in _SCOPE_BUCKETS:
            raise PKMError(f"unknown scope: {scope!r}", hint=f"Choose from: {list(_SCOPE_BUCKETS)}")

        conn = connect(root)
        try:
            if full:
                _drop_all(conn)

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
            else:
                files = _walk_files(root.resolve(), _SCOPE_BUCKETS[scope])

            indexed = 0
            skipped = 0
            for bucket, abs_p in files:
                if _index_one(conn, root.resolve(), bucket, abs_p, embedder, vec_opt):
                    indexed += 1
                else:
                    skipped += 1
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
