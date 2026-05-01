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


def post_mutation(root: Path, event: LogEvent,
                  paths: list[str] | None = None) -> str | None:
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
