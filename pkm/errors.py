"""PKM exception hierarchy.

All user-facing errors derive from PKMError. Each carries a stable `code`
suitable for JSON output and a `hint` field for actionable user guidance.

Spec reference: §3.1 (error JSON shape), §5.7 (failure mode codes).
"""

from __future__ import annotations


class PKMError(Exception):
    """Base for all PKM errors."""

    code: str = "PKM_ERROR"

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


# M5 error codes — constants used by future raisers (M5.6/M5.7) and by tests.
EMBED_MODEL_MISSING = "EMBED_MODEL_MISSING"
RERANK_MODEL_MISSING = "RERANK_MODEL_MISSING"
EXPAND_FAILED = "EXPAND_FAILED"


class PKMConfigError(PKMError):
    """Configuration is invalid or contradictory."""

    code = "CONFIG_ERROR"


class PKMValidationError(PKMError):
    """User input or persisted data fails validation."""

    code = "VALIDATION_ERROR"


class PKMCitationNotDerived(PKMValidationError):
    """Body cites a path that isn't in `derived_from`."""

    code = "CITATION_NOT_DERIVED"


class PKMDerivedNotCited(PKMValidationError):
    """`derived_from` has a path that body never cites."""

    code = "DERIVED_NOT_CITED"


class PKMUngroundedWriting(PKMValidationError):
    """Body length exceeds the grounding threshold but has no citations."""

    code = "UNGROUNDED_WRITING"


class PKMStateError(PKMError):
    """System is in an unexpected state (file missing, invalid status, etc.)."""

    code = "STATE_ERROR"


class PKMNotFoundError(PKMError):
    """Requested resource (file, slug, topic) does not exist."""

    code = "NOT_FOUND"


class PKMNotImplementedError(PKMError):
    """Code path is reserved for a future milestone."""

    code = "NOT_IMPLEMENTED"


class PKMStatusError(PKMError):
    """A status-transition gate failed (e.g. promote requires reviewed)."""

    code = "STATUS_NOT_REVIEWED"


class PKMPromoteFromWritingNotYet(PKMNotImplementedError):
    code = "PROMOTE_FROM_WRITING_NOT_YET"


class PKMDemoteToWritingNotYet(PKMNotImplementedError):
    code = "DEMOTE_TO_WRITING_NOT_YET"


class PKMRerankModelMissing(PKMError):
    """Raised when bge-reranker-v2-m3 is not in the local cache."""

    code = "RERANK_MODEL_MISSING"


class PKMEmbedModelMissing(PKMError):
    """Raised when bge-m3 is not in the local cache (used by `pkm bench --real`)."""

    code = "EMBED_MODEL_MISSING"


class PKMExpandFailed(PKMError):
    """Raised when AI CLI query expansion fails (--expand path)."""

    code = "EXPAND_FAILED"


BOOTSTRAP_STEP_FAILED = "BOOTSTRAP_STEP_FAILED"


class PKMBootstrapStepFailed(PKMError):
    """A step inside `pkm bootstrap` exited non-zero."""

    code = "BOOTSTRAP_STEP_FAILED"


class PKMSampleInsufficientWiki(PKMError):
    """Raised when `pkm sample` cannot find ≥ 3 wiki notes to sample from."""

    code = "SAMPLE_INSUFFICIENT_WIKI"


class PKMIndexMissing(PKMStateError):
    """Raised when a command requires .pkm/index.db but it doesn't exist."""

    code = "INDEX_MISSING"


class PKMMigrationFailed(PKMStateError):
    """A migration's apply() raised, the runner rolled back, schema_version unchanged."""

    code = "MIGRATION_FAILED"


class PKMMigrationPending(PKMStateError):
    """schema_version < latest registered migration ID. Surfaced by `pkm doctor --strict`."""

    code = "MIGRATION_PENDING"


# ---------------------------------------------------------------------------
# M13 error classes
# ---------------------------------------------------------------------------

class PKMInfoError(PKMError):
    """Base for informational (non-failure) outcomes.

    exit_code = 0 means the CLI exits successfully even though a PKMError was
    raised. Rendered with an ``[INFO]`` prefix on stdout instead of
    ``Error [...]`` on stderr.
    """

    code = "PKM_INFO_ERROR"
    exit_code: int = 0


class PKMNotAGitRepo(PKMValidationError):
    """`pkm project link` invoked outside a git repo (and --allow-no-remote not set)."""

    code = "NOT_A_GIT_REPO"


class PKMAlreadyLinked(PKMInfoError):
    """Same git remote already registered to a project — idempotent NOOP."""

    code = "ALREADY_LINKED"


class PKMNotLinked(PKMStateError):
    """cwd does not resolve to any registered project."""

    code = "NOT_LINKED"


class PKMProjectIdConflict(PKMValidationError):
    """--id <slug> already in use."""

    code = "PROJECT_ID_CONFLICT"


class PKMInvalidProjectId(PKMValidationError):
    """Project id contains characters outside [a-z0-9-]."""

    code = "INVALID_PROJECT_ID"


class PKMMissingProjectField(PKMValidationError):
    """File under data/projects/<id>/** without `project` frontmatter or with mismatched value."""

    code = "MISSING_PROJECT_FIELD"


class PKMInvalidCategory(PKMValidationError):
    """`category` value not in {decisions, pitfalls, snippets, qna, notes}."""

    code = "INVALID_CATEGORY"


class PKMCategoryPathMismatch(PKMValidationError):
    """File path's category dir differs from frontmatter `category`."""

    code = "CATEGORY_PATH_MISMATCH"


class PKMOrphanProjectDir(PKMStateError):
    """data/projects/<id>/index.md missing or has empty git_remotes."""

    code = "ORPHAN_PROJECT_DIR"


class PKMSimilarKnowledgeCandidate(PKMInfoError):
    """Two project knowledge items have cosine similarity >= 0.92.

    Informational — surfaces pairs to consolidate; does not indicate state
    corruption. exit_code = 0 (inherited from PKMInfoError).
    """

    code = "SIMILAR_KNOWLEDGE_CANDIDATE"


# ---------------------------------------------------------------------------
# M14 error classes
# ---------------------------------------------------------------------------

class PKMCorruptTranscript(PKMValidationError):
    """jsonl parse failed."""

    code = "CORRUPT_TRANSCRIPT"


class PKMInstallMissing(PKMStateError):
    """`pkm install --for claude-code` not run on this PC; --strict doctor fails."""

    code = "PKM_INSTALL_MISSING"


def all_error_codes() -> dict[str, type[PKMError]]:
    """Return ``{code: cls}`` for every PKMError subclass reachable from this module.

    Walks the subclass tree recursively. The base ``PKMError`` itself is
    included (its code is ``"PKM_ERROR"``). Used by the registry test and the
    failure-mode matrix to enumerate the stable code surface.
    """
    out: dict[str, type[PKMError]] = {}

    def _walk(cls: type[PKMError]) -> None:
        out.setdefault(cls.code, cls)
        for sub in cls.__subclasses__():
            _walk(sub)

    _walk(PKMError)
    return out
