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
