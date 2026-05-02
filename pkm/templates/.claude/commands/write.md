# /write

Author a new writing draft from search seed, chunks topic, or freeform.

1. Decide the seed: search query (`--from-search "OAuth 토큰 저장"`), chunks topic (`--from-chunks oauth-deep-dive`), or none (freeform).
2. `pkm write new --slug <s> [--from-search "..." | --from-chunks <topic>] --purpose <guideline|report|summary|essay> --json`. The file lands at `data/writing/<s>.md` with frontmatter only (empty body).
3. Fill the body using `Edit` (writing is allow-writable per `.claude/settings.json`):
   - If `--from-search`: run `pkm search "<seed>" --json -n 5`, Read the top hits, synthesize.
   - If `--from-chunks`: Read every file in `derived_from`, synthesize.
   - Freeform: write from scratch.
4. Cite sources inline using `[<path>]` per spec §4.2 Citation contract — same as `/ask`.
5. Update `derived_from` if you cited additional paths beyond what `pkm write new` seeded.
6. `pkm write set-status <s> final` once content is review-ready.
7. `pkm promote data/writing/<s>.md --to <bucket>` to publish into wiki.

Workflow detail: SCHEMA.md § Workflows → "Write" + "Chunk → Wiki Synthesis".
