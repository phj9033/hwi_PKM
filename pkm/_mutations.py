"""Single chokepoint for the auto side-effects every mutation must trigger.

M2: append-to-log + rebuild-index.
M3: + reindex-changed-paths (only when caller passes `paths`).
M3.5: + git auto-commit (always — non-git dirs warn-and-skip).

`paths` is the second arg, not a LogEvent field, because LogEvent is the
persisted log.md row shape. `paths` is ephemeral — purely for routing the
reindex side-effect AND for staging the right files in the git commit.

Returns the new git commit SHA, or None when no commit was created (no-git
repo, or nothing to commit). Callers fold this into their JSON output.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from pkm.store import git as gitmod
from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect
from pkm.store.log import LogEvent, append_event
from pkm.store.toc import rebuild_index

_LOG_REL = "data/log.md"
_INDEX_REL = "data/index.md"


def post_mutation(root: Path, event: LogEvent, paths: list[str] | None = None) -> str | None:
    """Append event → rebuild TOC → reindex paths → git commit.

    Returns the 40-char commit SHA, or None if no commit was made (no git
    repo, or nothing to commit). Reindex failures are swallowed as warnings
    (filesystem is the source of truth); git failures likewise warn-and-skip.
    """
    append_event(root, event)
    rebuild_index(root)

    if paths:
        try:
            reindex_changed_paths(root, list(paths))
        except Exception as e:
            print(f"warning: post_mutation reindex failed: {e}", file=sys.stderr)
            if "PKM_DEBUG" in os.environ:
                traceback.print_exc(file=sys.stderr)

    return _git_commit_for(root, event, list(paths) if paths else [])


def reindex_changed_paths(root: Path, paths: list[str]) -> None:
    from pkm.commands.reindex import _bucket_for, _index_one, _vec_opted_in
    from pkm.search.tokenizer import detect_active, get_tokenizer

    conn = connect(root)
    try:
        # Mirror `pkm reindex db`: pick the indexing path from the DB's active
        # tokenizer/columns, not the _index_one defaults. Without this the
        # incremental path assumes a pre-m002 contentless FTS and fails on a
        # post-m002 (kiwi) content-table FTS with "no column named text".
        active = detect_active(conn)
        post_m002 = active == "kiwi"
        tokenizer = get_tokenizer(active) if post_m002 else None
        chunks_columns = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
        post_m003 = "project" in chunks_columns

        embedder = get_embedder()
        vec_opt = _vec_opted_in(root)
        for rel in paths:
            abs_p = root / rel
            if not abs_p.exists():
                continue
            bucket = _bucket_for(root, abs_p)
            if bucket is None:
                continue
            _index_one(
                conn,
                root,
                bucket,
                abs_p,
                embedder,
                vec_opt,
                post_m002=post_m002,
                post_m003=post_m003,
                tokenizer=tokenizer,
            )
        # Post-m002 content-table FTS5 doesn't auto-sync on chunks UPDATEs;
        # a single 'rebuild' after the loop resyncs it (matches reindex_db).
        if post_m002:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


def _git_commit_for(root: Path, event: LogEvent, paths: list[str]) -> str | None:
    """Stage paths + log + index, commit with `pkm <type>: <ref>` message."""
    if not gitmod.is_git_repo(root):
        print("warning: not a git repo, skipping commit", file=sys.stderr)
        return None
    stage = [*list(paths), _LOG_REL, _INDEX_REL]
    message = f"pkm {event.type}: {event.ref}"
    try:
        return gitmod.commit_paths(root, stage, message)
    except Exception as e:
        print(f"warning: git commit failed: {e}", file=sys.stderr)
        if "PKM_DEBUG" in os.environ:
            traceback.print_exc(file=sys.stderr)
        return None
