# /lint

Run the deterministic lint and (optionally) auto-fix the spec-marked items.

1. `pkm lint --json` — see all findings.
2. `pkm lint --errors-only --json` — for a CI-style hard-gate (exits 1 on errors only).
3. `pkm lint --fix --json` — auto-fix `MISSING_FIELD` (created_at, slug) and `ORPHAN_PROMOTED_SOURCE`. Other findings need human attention.

Lint codes (spec §6.5):
- Errors: MISSING_FIELD, INVALID_VALUE, DUPLICATE_SLUG, BROKEN_WIKILINK, BROKEN_DERIVED_FROM, ORPHAN_PROMOTED_SOURCE
- Warnings: STALE_DRAFT, STALE_STUB, ORPHAN_WIKI, LARGE_CHUNK_NEVER_PROMOTED, LANG_INCONSISTENT, RAW_BODY_MUTATED, BROKEN_CITATION, MISSING_LINK_CANDIDATE, CITATION_NOT_DERIVED, DERIVED_NOT_CITED, UNGROUNDED_WRITING

The four trailing codes are M11 writing grounding warnings — `pkm promote` enforces them as hard gates.

Workflow detail: SCHEMA.md § Workflows → "Lint".
