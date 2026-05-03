"""Hard gate on fast-suite wall-time. RSS gate lives in conftest.py."""

from __future__ import annotations

import os

import pytest

# Hard upper bound on the fast suite wall time. The §9.4 target is < 120s
# locally; we add 60s of CI runner slack. If you trip this, the suite has
# regressed: profile, don't bump.
WALL_TIME_BUDGET_SECONDS = 180.0


def test_fast_suite_wall_time_within_budget(_session_clock):
    elapsed = _session_clock.elapsed_so_far()
    if os.environ.get("PKM_PERF_GATE_OFF") == "1":
        pytest.skip("PKM_PERF_GATE_OFF=1 — skipping wall-time fence")
    assert elapsed < WALL_TIME_BUDGET_SECONDS, (
        f"fast suite wall-time {elapsed:.1f}s exceeded budget {WALL_TIME_BUDGET_SECONDS:.0f}s"
    )
