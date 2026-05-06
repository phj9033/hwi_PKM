# /write

Author a new writing draft from search seed, chunks topic, or freeform.

1. Decide the seed: search query (`--from-search "OAuth 토큰 저장"`), chunks topic (`--from-chunks oauth-deep-dive`), or none (freeform).
2. `pkm write new --slug <s> [--from-search "..." | --from-chunks <topic>] --purpose <guideline|report|summary|essay> --json`. The file lands at `data/writing/<s>.md` with frontmatter only (empty body).
3. Fill the body using `Edit` (writing is allow-writable per `.claude/settings.json`):
   - If `--from-search`: run `pkm search "<seed>" --json -n 5`, Read the top hits, synthesize.
   - If `--from-chunks`: Read every file in `derived_from`, synthesize.
   - Freeform: write from scratch.
4. Cite sources inline using `[<path>]` (V1 §4.2 Citation contract). Every `derived_from` path MUST be cited inline at least once (else `pkm promote` raises `DERIVED_NOT_CITED`). Conversely, every inline `[data/...]` you add must be in `derived_from` (else `CITATION_NOT_DERIVED`). For long-form bodies (≥ 400 chars), at least one citation is required; set `purpose: essay` or `grounding_exempt: true` in frontmatter to opt out intentionally.
5. Update `derived_from` if you cited additional paths beyond what `pkm write new` seeded. The `--from-search` JSON output now includes a `related_suggestions` block (semantically-close wiki pages from MISSING_LINK_CANDIDATE) — review and pull any that strengthen evidence into `derived_from`.
6. `pkm write set-status <s> final` once content is review-ready.
7. `pkm promote data/writing/<s>.md --to <bucket>` to publish into wiki.

   Failure modes (V2 M11 grounding gate):
   - `CITATION_NOT_DERIVED` — body cites a path not in `derived_from`
   - `DERIVED_NOT_CITED`    — `derived_from` has a path body never cites
   - `UNGROUNDED_WRITING`   — body ≥ 400 chars but zero citations
   - `BROKEN_CITATION`      — cited path doesn't exist on disk

Workflow detail: SCHEMA.md § Workflows → "Write" + "Chunk → Wiki Synthesis".
