# /research <topic>

Multi-source research. Parallel WebSearch + WebFetch + N captures.

1. Run a few WebSearch queries to fan out on the topic.
2. WebFetch the most relevant 3–6 URLs.
3. For each: `pkm capture create --slug <kebab> --title "<title>" --url <url> --status draft --json`.
4. Optionally bundle related sources into a chunk: `pkm chunks new <topic>` and `pkm chunks add <topic> <files>`.

Workflow detail: SCHEMA.md § Workflows → "Research".
