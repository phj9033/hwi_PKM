<!-- pkm:start managed by pkm install -->
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Quick check: is `.pkm-link` present in cwd? If not, silently proceed. No PKM call, no user-facing output.
2. If marker exists, run `pkm project current --json 2>/dev/null`.
3. If `ok: true`: invoke the `pkm:recalling-project-context` skill — it loads the project's index.md and recent decisions/pitfalls into context.
4. If marker exists but `ok: false` (stale marker, env misconfig, pkm missing): silently proceed. Do not surface unless the user asks about PKM.

The marker `.pkm-link` is created by `pkm project link` and contains the project_id. Run `pkm doctor --fix` from a project cwd to repair drift. Recommended to gitignore (per-machine link state).
<!-- pkm:end managed by pkm install -->
