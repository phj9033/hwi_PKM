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
