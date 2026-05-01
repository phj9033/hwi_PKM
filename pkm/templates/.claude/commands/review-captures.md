# /review-captures

Sweep all draft captures and either move them to `reviewed` or recommend deletion.

1. `pkm capture list --status draft --json` → iterate.
2. `pkm capture show <slug>` → inspect each.
3. For each capture, decide:
   - keep & promote later → `pkm capture set-status <slug> reviewed`
   - drop                 → `pkm capture rm <slug>`

Workflow detail: SCHEMA.md § Workflows → "Review Captures".
