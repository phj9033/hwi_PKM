---
description: PKM project management — link, current, list, show.
allowed-tools: Bash
---

User has invoked `/pkm-project $ARGUMENTS`. Parse the verb:
- `link [--id <slug>]` → run `pkm project link [--id <slug>]` and report result.
- `current` → run `pkm project current --json` and pretty-print.
- `list` → run `pkm project list` and show.
- `show <id>` → run `pkm project show <id>` and show.

This is a thin CLI wrapper — no skill invocation needed.
