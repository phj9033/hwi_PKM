<!-- pkm:start managed by pkm install -->
## PKM project context loading

When you start working in a directory, **before** any non-trivial work, run this one-liner from the cwd:

```sh
[ -f .pkm-link ] && pkm project current --json 2>/dev/null; :
```

Then act on the result:

1. **No output** (marker absent, or `pkm` not on PATH): silently proceed. No further PKM call, no user-facing output.
2. **`{"ok": true, ...}`**: invoke the `pkm:recalling-project-context` skill — it loads the project's `index.md` and recent decisions/pitfalls into context.
3. **`{"ok": false, ...}`** (stale marker, env misconfig): silently proceed. Do not surface unless the user asks about PKM.

Notes:
- The trailing `; :` forces exit 0 so the bootstrap never surfaces as an error in unlinked repos like `hwi_PKM_data`.
- The marker `.pkm-link` is created by `pkm project link` and contains the project_id. Run `pkm doctor --fix` from a project cwd to repair drift. Recommended to gitignore (per-machine link state).
- This block is managed by `pkm install` and is portable across machines — only assumes `pkm` is on PATH.
<!-- pkm:end managed by pkm install -->
