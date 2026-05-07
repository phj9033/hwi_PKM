from pkm.session.adapters.base import SessionAdapter, SessionRef, NormalizedTranscript, NormalizedMessage
from pkm.session.adapters.claude_code import ClaudeCodeAdapter

ADAPTERS: dict[str, type[SessionAdapter]] = {
    "claude_code": ClaudeCodeAdapter,
}
