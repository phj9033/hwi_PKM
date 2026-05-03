"""Reflective gate over `pkm.errors`.

Every PKMError subclass must:
1. Have a unique non-empty uppercase `code` attribute.
2. Be reachable from `all_error_codes()`.
3. Have a registered minimal-construction scenario in `SCENARIOS`.
4. Round-trip through `to_dict()` with the documented shape.

When a new PKMError subclass is added, this file must be updated. The
matrix test (`tests/test_failure_mode_matrix.py`) iterates over the same
set, so adding a class without a scenario is caught here first.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from pkm.errors import (
    BOOTSTRAP_STEP_FAILED,  # noqa: F401 (re-exported constant)
    EMBED_MODEL_MISSING,  # noqa: F401
    EXPAND_FAILED,  # noqa: F401
    RERANK_MODEL_MISSING,  # noqa: F401
    PKMBootstrapStepFailed,
    PKMConfigError,
    PKMDemoteToWritingNotYet,
    PKMEmbedModelMissing,
    PKMError,
    PKMExpandFailed,
    PKMNotFoundError,
    PKMNotImplementedError,
    PKMPromoteFromWritingNotYet,
    PKMRerankModelMissing,
    PKMStateError,
    PKMStatusError,
    PKMValidationError,
    all_error_codes,
)

CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Each error class → minimal construction scenario.
# When you add a new PKMError subclass, add an entry here.
SCENARIOS: dict[str, Callable[[], PKMError]] = {
    "PKM_ERROR": lambda: PKMError("base error", hint="base hint"),
    "CONFIG_ERROR": lambda: PKMConfigError("bad config"),
    "VALIDATION_ERROR": lambda: PKMValidationError("bad input"),
    "STATE_ERROR": lambda: PKMStateError("inconsistent state"),
    "NOT_FOUND": lambda: PKMNotFoundError("missing thing"),
    "NOT_IMPLEMENTED": lambda: PKMNotImplementedError("future"),
    "STATUS_NOT_REVIEWED": lambda: PKMStatusError("requires reviewed"),
    "PROMOTE_FROM_WRITING_NOT_YET": lambda: PKMPromoteFromWritingNotYet("future"),
    "DEMOTE_TO_WRITING_NOT_YET": lambda: PKMDemoteToWritingNotYet("future"),
    "RERANK_MODEL_MISSING": lambda: PKMRerankModelMissing("model missing"),
    "EMBED_MODEL_MISSING": lambda: PKMEmbedModelMissing("model missing"),
    "EXPAND_FAILED": lambda: PKMExpandFailed("expand failed"),
    "BOOTSTRAP_STEP_FAILED": lambda: PKMBootstrapStepFailed("step failed"),
}


def test_all_codes_are_uppercase_identifiers():
    for code in all_error_codes():
        assert CODE_RE.match(code), f"code {code!r} is not [A-Z][A-Z0-9_]*"


def test_codes_are_unique():
    codes = list(all_error_codes())
    assert len(codes) == len(set(codes)), f"duplicate codes: {codes}"


def test_scenarios_cover_every_class_no_extras():
    """Every PKMError subclass has a scenario — and no extras."""
    actual = set(all_error_codes())
    documented = set(SCENARIOS)
    missing = actual - documented
    extra = documented - actual
    assert not missing, f"missing scenarios for: {sorted(missing)}"
    assert not extra, f"extra scenarios (no matching class): {sorted(extra)}"


@pytest.mark.parametrize("code", sorted(SCENARIOS))
def test_scenario_constructs_with_documented_code(code: str):
    err = SCENARIOS[code]()
    assert isinstance(err, PKMError)
    assert err.code == code, f"{type(err).__name__}.code = {err.code!r}, expected {code!r}"


@pytest.mark.parametrize("code", sorted(SCENARIOS))
def test_to_dict_shape(code: str):
    err = SCENARIOS[code]()
    d = err.to_dict()
    assert set(d.keys()) == {"code", "message", "hint"}
    assert d["code"] == code
    assert isinstance(d["message"], str) and d["message"]
    assert d["hint"] is None or (isinstance(d["hint"], str) and d["hint"])
