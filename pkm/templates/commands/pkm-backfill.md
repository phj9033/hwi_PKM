---
description: Bulk-extract knowledge from historical Claude Code sessions for a project.
allowed-tools: Bash, Read, Edit, Write
---

User has invoked `/pkm-backfill $ARGUMENTS`. Parse args:
- `--project <id>` — target a specific project (default = current cwd-resolved)
- `--since <YYYY-MM-DD>` — cutoff date
- `--min-messages <N>` — override default 5
- `--limit <N>` — process at most N sessions

Invoke the `pkm:backfilling-sessions` skill with these args.
