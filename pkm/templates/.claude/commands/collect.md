# /collect <url|text>

Collect a single source into `data/raw/captures/` with rich enrichment.

For a URL the flow is: fetch best-quality body → attach discussion
context → LLM-summarize → capture. For raw text, skip the fetch step.

## Steps

1. **Body**. If input is a URL:
   - Try `WebFetch` first (cheap, no shell).
   - If the body is empty, suspiciously short (<200 chars), or looks
     JS-blocked, fall back to: `pkm adapter auto "$URL"`
     (auto-routes to youtube / openalex / jina based on the host).
   For non-URL input: treat the text as the body directly.

2. **Discussion** (URLs only, best-effort — empty output is OK):
   - `pkm adapter hn "$URL"`
   - `pkm adapter reddit "$URL"`

3. **LLM post-processing** (stdin → stdout, both can be empty on failure):
   - `tldr=$(printf '%s' "$body" | pkm enrich tldr)`
   - `tags=$(printf '%s' "$body" | pkm enrich tags)`   # JSON array

4. **Title + slug**. Infer a concise title and kebab-case slug from
   `<h1>` or `<title>` of the body. Date prefix is auto-added.

5. **Capture**. Pipe the assembled body into:
   ```
   printf "## TL;DR\n%s\n\n%s\n\n%s\n\n%s" "$tldr" "$body" "$hn" "$reddit" \
     | pkm capture create \
         --slug <kebab-title> \
         --title "<title>" \
         --url <url-if-any> \
         --tags "$tags" \
         --summary "$tldr" \
         --status draft --json
   ```

6. Echo the returned `path`.

Workflow detail: SCHEMA.md § Workflows → "Collect".
