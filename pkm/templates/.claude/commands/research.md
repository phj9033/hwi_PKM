# /research <topic>

Multi-source research. Parallel `WebSearch` + `pkm adapter auto`
+ enrichment + N captures, optionally bundled into a chunk.

## Steps

1. **Fan out**. Run a few `WebSearch` queries on the topic to gather
   candidate URLs. Pick the top 3–6 by relevance.

2. **Per URL**, run the same chain as `/collect`:
   - `body=$(pkm adapter auto "$URL")` (with WebFetch as fast-path).
   - `hn=$(pkm adapter hn "$URL")`, `reddit=$(pkm adapter reddit "$URL")`.
   - `tldr=$(printf '%s' "$body" | pkm enrich tldr)`
   - `tags=$(printf '%s' "$body" | pkm enrich tags)`
   - `printf "## TL;DR\n%s\n\n%s\n\n%s\n\n%s" "$tldr" "$body" "$hn" "$reddit" \
        | pkm capture create --slug <kebab> --title "<title>" --url "$URL" \
                             --tags "$tags" --summary "$tldr" --status draft --json`

3. **Bundle**. Group the resulting captures into a topic chunk:
   - `pkm chunks new <topic-slug>`
   - `pkm chunks add <topic-slug> <each-capture-path>`

4. **Suggest related wiki pages**. Read the chunk README, pipe through:
   - `pkm enrich related` (newline-separated slug candidates).

Workflow detail: SCHEMA.md § Workflows → "Research".
