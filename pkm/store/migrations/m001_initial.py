"""m001 — baseline marker for the V1 schema. No-op apply (schema is already
created by `pkm.store.index_db.connect`)."""

from __future__ import annotations

ID = 1
DESCRIPTION = "v1 baseline schema (documents, chunks, *_fts, *_vec, links)"


def check(conn) -> dict:
    return {"needed": False, "reason": "v1 schema is created by index_db.connect"}


def apply(conn) -> dict:
    return {"ok": True, "no_op": True}
