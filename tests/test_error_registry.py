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
    PKMAlreadyLinked,
    PKMBootstrapStepFailed,
    PKMCategoryPathMismatch,
    PKMCitationNotDerived,
    PKMConfigError,
    PKMCorruptTranscript,
    PKMDemoteToWritingNotYet,
    PKMDerivedNotCited,
    PKMEmbedModelMissing,
    PKMError,
    PKMExpandFailed,
    PKMIndexMissing,
    PKMInfoError,
    PKMInstallMissing,
    PKMInvalidCategory,
    PKMInvalidProjectId,
    PKMMigrationFailed,
    PKMMigrationPending,
    PKMMissingProjectField,
    PKMNotAGitRepo,
    PKMNotFoundError,
    PKMNotImplementedError,
    PKMNotLinked,
    PKMOrphanProjectDir,
    PKMProjectIdConflict,
    PKMPromoteFromWritingNotYet,
    PKMRerankModelMissing,
    PKMSampleInsufficientWiki,
    PKMSimilarKnowledgeCandidate,
    PKMStateError,
    PKMStatusError,
    PKMUngroundedWriting,
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
    "SAMPLE_INSUFFICIENT_WIKI": lambda: PKMSampleInsufficientWiki(
        "wiki 카드 부족", hint="/promote 로 늘리세요"
    ),
    "INDEX_MISSING": lambda: PKMIndexMissing(
        "no search index found at .pkm/index.db",
        hint="Run `pkm reindex db --full` first.",
    ),
    "CITATION_NOT_DERIVED": lambda: PKMCitationNotDerived(
        "body cites paths not in derived_from",
        hint="add the cited path(s) to derived_from or remove the citation.",
    ),
    "DERIVED_NOT_CITED": lambda: PKMDerivedNotCited(
        "derived_from paths never cited in body",
        hint="cite each derived_from path inline or remove unused entries.",
    ),
    "UNGROUNDED_WRITING": lambda: PKMUngroundedWriting(
        "body length exceeds threshold but has no citations",
        hint="cite at least one source or set grounding_exempt: true.",
    ),
    "MIGRATION_FAILED": lambda: PKMMigrationFailed(
        "migration 2 failed: forced",
        hint="re-run with `pkm migrate --check` to see remaining work.",
    ),
    "MIGRATION_PENDING": lambda: PKMMigrationPending(
        "schema_version 1 < latest 2",
        hint="run `pkm migrate --apply`.",
    ),
    # M13 additions
    "PKM_INFO_ERROR": lambda: PKMInfoError("info message"),
    "NOT_A_GIT_REPO": lambda: PKMNotAGitRepo(
        "not inside a git repository",
        hint="run from within a git repo or pass --allow-no-remote.",
    ),
    "ALREADY_LINKED": lambda: PKMAlreadyLinked(
        "remote already linked to project hwi-pkm",
        hint="nothing to do — this remote is already registered.",
    ),
    "NOT_LINKED": lambda: PKMNotLinked(
        "cwd is not inside any registered project",
        hint="run `pkm project link` to register this repo.",
    ),
    "PROJECT_ID_CONFLICT": lambda: PKMProjectIdConflict(
        "project id 'x' is already in use",
        hint="choose a different --id or remove the existing project first.",
    ),
    "INVALID_PROJECT_ID": lambda: PKMInvalidProjectId(
        "project id 'Bad Slug!' contains invalid characters",
        hint="use only lowercase letters, digits, and hyphens.",
    ),
    "MISSING_PROJECT_FIELD": lambda: PKMMissingProjectField(
        "file missing required 'project' frontmatter field",
        hint="add 'project: <id>' to the frontmatter.",
    ),
    "INVALID_CATEGORY": lambda: PKMInvalidCategory(
        "category 'nope' is not valid",
        hint="use one of: decisions, pitfalls, snippets, qna, notes.",
    ),
    "CATEGORY_PATH_MISMATCH": lambda: PKMCategoryPathMismatch(
        "file is in 'decisions/' but frontmatter says category: pitfalls",
        hint="move the file to the correct directory or fix the frontmatter.",
    ),
    "ORPHAN_PROJECT_DIR": lambda: PKMOrphanProjectDir(
        "data/projects/orphaned has no index.md",
        hint="create an index.md or remove the directory.",
    ),
    "SIMILAR_KNOWLEDGE_CANDIDATE": lambda: PKMSimilarKnowledgeCandidate(
        "two knowledge items have similarity >= 0.92",
        hint="review and merge or differentiate the similar items.",
    ),
    "CORRUPT_TRANSCRIPT": lambda: PKMCorruptTranscript(
        "invalid jsonl at line 1: Expecting value",
        hint="re-save the transcript or pkm session forget <uuid>.",
    ),
    "PKM_INSTALL_MISSING": lambda: PKMInstallMissing(
        "claude-code: not installed",
        hint="run `pkm install --for claude-code --data-repo <path>`.",
    ),
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
