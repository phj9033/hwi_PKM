# /promote

Promote a reviewed capture into a wiki bucket.

1. Confirm the capture is `status: reviewed`. If not: `pkm capture set-status <ref> reviewed`.
2. Pick a bucket: `concepts | entities | notes | reports`.
3. (Optional) Pick a target slug: by default the date prefix is stripped from the capture slug.
4. Run: `pkm promote <ref> --to <bucket> [--slug NEW_SLUG] [--keep-source] --json`.
5. The wiki page lands at `data/wiki/<bucket>/<slug>.md` with `status: stub` and `promoted_from: <source>`.

For writing → wiki promotion, the M11 grounding gate runs before write. Failure modes:

- `CITATION_NOT_DERIVED` — body cites a path not in `derived_from`. Fix: add the path to `derived_from`, or remove the inline `[<path>]`.
- `DERIVED_NOT_CITED` — `derived_from` has a path body never cites. Fix: cite each derived path inline at least once, or trim unused entries.
- `UNGROUNDED_WRITING` — body ≥ 400 chars but no citations. Fix: cite at least one source, or set `purpose: essay` / `grounding_exempt: true` if intentional.
- `BROKEN_CITATION` — cited path doesn't exist. Fix the path or remove the citation.

Workflow detail: SCHEMA.md § Workflows → "Promote".
