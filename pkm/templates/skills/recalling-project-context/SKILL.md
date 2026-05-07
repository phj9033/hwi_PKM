---
name: pkm:recalling-project-context
description: Use at the start of work in any project (after the CLAUDE.md instruction) or whenever the user references prior decisions, patterns, or pitfalls in their codebase. Loads project knowledge from the linked PKM data repo. Self-resolves the current project from cwd; do NOT hardcode project ids.
---

# pkm:recalling-project-context

Loads the user's project knowledge into your context so you can ground recommendations in prior decisions, avoid known pitfalls, and reuse vetted snippets.

## When to use

- At the very start of a coding session in any cwd (the global CLAUDE.md instruction triggers you).
- Mid-session, when the user mentions a topic that may have prior PKM coverage ("OAuth", "the auth migration we did", "remember the rate limit fix").

## When NOT to use

- The user is doing throwaway work or asking general questions not tied to their codebase.
- The cwd is not a linked PKM project (the skill exits silently in that case — do not surface).

## Steps

1. **Resolve current project** (do this every time — never hardcode project ids):
   ```bash
   pkm project current --json
   ```
   - If `ok: false` and `code: NOT_LINKED` → silently end. Do not mention PKM unless the user asks.
   - If `ok: true` → record `project_id` and proceed.

2. **Inject project index**:
   ```bash
   pkm context inject --max-tokens 600 --json
   ```
   The output `content` field is a Markdown summary of the project's recent decisions, pitfalls, snippets. Read it carefully — it represents what your past sessions have decided.

3. **(Optional) On-demand deeper recall** if the user has stated a specific topic for the work:
   ```bash
   pkm search "<user's topic>" --scope project --json -n 5
   ```
   For each hit, you may `Read` the file path to ground your work. See `search-scope-guidelines.md` in this skill for which scope to pick.

4. **One-line acknowledgment** to the user:
   > "Loaded project context for `<project_id>`: N decisions, M pitfalls, K snippets indexed. Will ground recommendations against these."

   Do NOT dump the full index.md content into chat — you've already absorbed it.

## Portability rules (from spec §8.2)

- **Always** call `pkm project current --json` first. The project resolves from cwd dynamically — same skill works in every project on every PC.
- **Never** hardcode paths like `~/Documents/pkm/...`. Always use `pkm` CLI output to discover paths.
- **Never** use `Edit`/`Write` to mutate `data/projects/**` directly — always go through `pkm project knowledge add` (handled by other skills, not this one — this skill only reads).

## See also

- `search-scope-guidelines.md` — choosing `--scope wiki|project|projects|all`.
- `pkm:extracting-session-knowledge` — the inverse skill, used at end of session.
