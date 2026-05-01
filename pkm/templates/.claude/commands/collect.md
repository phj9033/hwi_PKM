# /collect <url|text>

Collect a single source into `data/raw/captures/`.

1. If input is a URL: WebFetch it; otherwise treat input as raw text.
2. Summarize in 1–3 sentences and infer 1–4 tags.
3. Run: `pkm capture create --slug <kebab-title> --title "<title>" --url <url-if-any> --status draft --json` (pipe the body through stdin).
4. Echo the returned `path`.

Workflow detail: SCHEMA.md § Workflows → "Collect".
