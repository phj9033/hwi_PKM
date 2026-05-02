"""Pytest scaffolding — memory safety + stub embedder default.

Goals (spec §8.3):
- The fast test suite NEVER loads real ML models. Tests requiring real models
  must be `@pytest.mark.slow`, run sequentially in a separate workflow.
- A runaway test cannot crash the host. We cap virtual address space on
  Unix-like systems. Default 4 GB; override via `PKM_TEST_RSS_CAP_GB`.

This conftest runs before any test session — see pytest's discovery order.
"""

from __future__ import annotations

import os
import resource


def _apply_rss_cap() -> None:
    """Cap process virtual memory to prevent runaway tests from OOMing the host.

    Unix only. Best-effort: we lower the soft limit but never raise it.
    """
    if not hasattr(resource, "RLIMIT_AS"):
        return
    try:
        cap_gb = float(os.environ.get("PKM_TEST_RSS_CAP_GB", "4"))
    except ValueError:
        cap_gb = 4.0
    cap_bytes = int(cap_gb * 1024**3)
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)

    new_soft: int
    if soft == resource.RLIM_INFINITY:
        new_soft = cap_bytes
    else:
        new_soft = min(soft, cap_bytes)

    if hard != resource.RLIM_INFINITY and new_soft > hard:
        new_soft = hard

    try:
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))
    except (ValueError, OSError):
        # Some sandboxed environments refuse setrlimit. Don't crash the suite.
        pass


# Default the stub embedder and reranker ON — real models must be opt-in via slow tests.
os.environ.setdefault("PKM_TEST_STUB_EMBEDDER", "1")
os.environ.setdefault("PKM_TEST_SKIP_DOWNLOAD", "1")
os.environ.setdefault("PKM_TEST_STUB_RERANKER", "1")

_apply_rss_cap()
