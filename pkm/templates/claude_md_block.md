<!-- pkm:start managed by pkm install -->
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Check if the cwd is a linked PKM project: run `pkm project current --json`.
2. If linked (`ok: true`): invoke the `pkm:recalling-project-context` skill — it loads the project's index.md and recent decisions/pitfalls into context.
3. If not linked (`code: NOT_LINKED`): silently proceed. Do not surface this to the user unless they ask about PKM.

This applies to any cwd, any project — the skill resolves which project automatically.
<!-- pkm:end managed by pkm install -->
