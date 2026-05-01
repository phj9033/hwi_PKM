"""Single chokepoint for the auto side-effects every mutation must trigger.

M2: append-to-log + rebuild-index.
M3: + reindex-changed-paths (only when caller passes `paths`).
M3.5: + git auto-commit (deferred).

`paths` is the second arg, not a LogEvent field, because LogEvent is the
persisted log.md row shape. `paths` is ephemeral — purely for routing the
reindex side-effect to the changed files.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect
from pkm.store.log import LogEvent, append_event
from pkm.store.toc import rebuild_index


def post_mutation(root: Path, event: LogEvent, paths: list[str] | None = None) -> None:
    """Append the event to log.md, regenerate index.md, then reindex changed paths.

    The reindex step is wrapped in try/except: the filesystem is the source of
    truth, so an index failure must NOT block a mutation. The user can recover
    via `pkm doctor` + `pkm reindex db --full`.

    `paths` is optional. M2 call sites that have not been migrated yet still
    work (log + TOC only); migrated call sites get reindex too.
    """
    append_event(root, event)
    rebuild_index(root)
    if not paths:
        return
    try:
        reindex_changed_paths(root, list(paths))
    except Exception as e:
        print(f"warning: post_mutation reindex failed: {e}", file=sys.stderr)
        if "PKM_DEBUG" in os.environ:
            traceback.print_exc(file=sys.stderr)


def reindex_changed_paths(root: Path, paths: list[str]) -> None:
    """Index only the given paths (relative to `root`). Lazy imports keep
    `pkm._mutations` cheap to import."""
    from pkm.commands.reindex import _bucket_for, _index_one, _vec_opted_in

    conn = connect(root)
    try:
        embedder = get_embedder()
        vec_opt = _vec_opted_in(root)
        for rel in paths:
            abs_p = root / rel
            if not abs_p.exists():
                continue
            bucket = _bucket_for(root, abs_p)
            if bucket is None:
                continue
            _index_one(conn, root, bucket, abs_p, embedder, vec_opt)
        conn.commit()
    finally:
        conn.close()
