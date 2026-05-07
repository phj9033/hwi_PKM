---
description: Extract knowledge from a Claude Code session into the current project's PKM.
allowed-tools: Bash, Read, Edit, Write
---

User has invoked `/pkm-extract-session $ARGUMENTS`. The argument (if any) is a session uuid.

Invoke the `pkm:extracting-session-knowledge` skill. Pass `$ARGUMENTS` as the optional session uuid. If empty, the skill resolves the current session via `CLAUDE_SESSION_ID` env or most-recent-today.

If the user passed `--auto-approve` as part of the args, switch to auto-approve mode (skip review rounds).
