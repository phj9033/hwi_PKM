# /promote

Promote a reviewed capture into a wiki bucket.

1. Confirm the capture is `status: reviewed`. If not: `pkm capture set-status <ref> reviewed`.
2. Pick a bucket: `concepts | entities | notes | reports`.
3. (Optional) Pick a target slug: by default the date prefix is stripped from the capture slug.
4. Run: `pkm promote <ref> --to <bucket> [--slug NEW_SLUG] [--keep-source] --json`.
5. The wiki page lands at `data/wiki/<bucket>/<slug>.md` with `status: stub` and `promoted_from: <source>`.

Workflow detail: SCHEMA.md § Workflows → "Promote".
