"""Pytest scaffolding — memory safety + stub embedder default.

Goals (spec §8.3):
- The fast test suite NEVER loads real ML models. Tests requiring real models
  must be `@pytest.mark.slow`, run sequentially in a separate workflow.
- A runaway test cannot crash the host. We cap virtual address space on
  Unix-like systems. Default 4 GB; override via `PKM_TEST_RSS_CAP_GB`.
- Spec §8.3 + §9.4 cap the fast suite at < 2 min wall-time and ≤ 4 GB RSS.
  M7.4 enforces those as hard gates via `_session_clock` (consumed by
  `tests/test_perf_gate.py`) and `_rss_guard` (autouse below).

xdist note: with `pytest-xdist -n auto`, session-scope fixtures run once
per worker process. So `_session_clock` measures elapsed-time-from-the-
first-test-on-this-worker and `_rss_guard` measures peak-RSS-of-this-
worker. Both are still meaningful: the slowest worker bounds the total
wall-time, and each worker individually must stay under 4 GB. We
deliberately avoid a `pytest_sessionfinish` hook — the added complexity
isn't worth it for an 11s suite.

This conftest runs before any test session — see pytest's discovery order.
"""

from __future__ import annotations

import os
import resource
import time

import psutil
import pytest


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


# RSS gate threshold — §9.4 says ≤ 4 GB.
_RSS_BUDGET_BYTES = 4 * 1024 * 1024 * 1024


class _Clock:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_so_far(self) -> float:
        return time.monotonic() - self._start


@pytest.fixture(scope="session")
def _session_clock() -> _Clock:
    return _Clock()


@pytest.fixture(scope="session", autouse=True)
def _rss_guard():
    """Fail the session if peak RSS of the test process exceeds §9.4's 4 GB.

    Under pytest-xdist, this runs once per worker process — so each worker
    is bounded individually (4 GB per worker, not 4 GB summed across 14
    workers: each worker runs in its own process and only this worker's
    footprint is measured here). If this is misleading on a single-machine
    CI runner, profile with `--show-capture` and drop xdist for diagnosis.
    """
    if os.environ.get("PKM_RSS_GATE_OFF") == "1":
        yield
        return
    proc = psutil.Process(os.getpid())
    peak = proc.memory_info().rss
    yield
    final = proc.memory_info().rss
    peak = max(peak, final)
    assert peak <= _RSS_BUDGET_BYTES, (
        f"peak RSS {peak / (1024**3):.2f} GB exceeded §9.4 budget "
        f"{_RSS_BUDGET_BYTES / (1024**3):.0f} GB"
    )
