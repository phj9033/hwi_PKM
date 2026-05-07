# Search Scope Guidelines

PKM search supports several scopes. Pick based on the user's intent.

| User intent | Scope |
|---|---|
| "What did we decide about X in this project?" | `--scope project` (current cwd-resolved project) |
| "Has anyone in any project dealt with X?" | `--scope projects` (all projects, no wiki) |
| "What's the canonical concept for X?" | `--scope wiki` (curated, general knowledge) |
| Mixed / unsure | (default) — when cwd is linked = wiki + current project; otherwise wiki + raw + writing |
| Cross-project pattern discovery | `--scope all` |

## When to override default

The default is usually right. Override only when:
- User explicitly says "search across all projects" → `--scope all` or `--scope projects`.
- User explicitly limits to general concepts → `--scope wiki`.
- Working in monorepo and explicit project context required → `--scope project:<id>`.
