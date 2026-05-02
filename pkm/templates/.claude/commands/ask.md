# /ask

Answer a question from the wiki, with citations.

1. Run `pkm search "<question>" --scope wiki -n 8 --json`. If `--expand` is configured (`.pkm/config.local.toml` has an `expand_query` task), prefer `--expand`.
2. Read the top results' files (`Read` tool) — body matters, not just snippet.
3. Synthesize an answer using ONLY content found in those files. Every factual claim ends with `[<wiki path>]`. Multiple sources: `[a.md][b.md]` or `[a.md, b.md]`.
4. If the search yields nothing relevant, say "관련 wiki 페이지가 없습니다. 먼저 `/collect` 또는 `/research` 로 자료를 모아주세요." and stop. Do NOT fall back on general knowledge.
5. Citation paths must be path-resolvable; `pkm lint` will flag broken citations (`BROKEN_CITATION` warning).
6. (Optional) If the answer is reusable, save it as a capture: `pkm capture create --slug <s> --title "<t>" --status draft` (stdin = answer body). Frontmatter `derived_from:` MUST list every cited path.

Citation contract: SCHEMA.md § Workflows → "Ask".
