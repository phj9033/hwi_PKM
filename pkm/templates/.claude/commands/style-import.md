# /style-import

Migrate one external blog post / Notion export into `data/style/<slug>.md` so the AI can use it as a tone reference for `/blog`.

## Args

`/style-import <slug>` — slug derived from URL or topic, e.g. `oauth-token-storage`. Slug must be lowercase, hyphen-separated, unique under `data/style/`.

## Steps

1. **Confirm slug + collect metadata.** Ask the user (or accept if pre-filled): `title`, `lang` (`ko`/`en`/`mixed`), `source_url` (optional), `tags` (optional list).
2. **Fetch the original.** Two paths:
   - If user provided `source_url`: try `WebFetch <source_url>`. On success, save the body to `raw-imports/style/<slug>.md` (create dir if needed). On failure (Naver Blog / login walls / JS-rendered sites), tell the user: "WebFetch 실패 — `raw-imports/style/<slug>.md` 에 본문을 직접 저장한 뒤 다시 호출해주세요." and STOP.
   - If user didn't provide URL: assume they've already saved the original at `raw-imports/style/<slug>.md`. Read it; if missing, instruct them to save it first and STOP.
3. **Synthesize sample.** Read `raw-imports/style/<slug>.md`, strip noise (nav/footer/comments/sidebar boilerplate), and write `data/style/<slug>.md` with the frontmatter shape:

   ```yaml
   ---
   slug: <slug>
   title: <title>
   lang: <ko|en|mixed>
   created_at: <ISO 8601 now()>
   updated_at: <ISO 8601 now()>
   source_url: <url-if-given>          # optional
   source_path: raw-imports/style/<slug>.md
   tags: [<tags>]                      # optional
   ---
   <cleaned body>
   ```

4. **Reindex + commit.**

   ```bash
   pkm reindex db --scope style --root .
   git add data/style/<slug>.md raw-imports/style/<slug>.md
   git commit -m "style: import <slug>"
   ```

5. **Verify.**

   ```bash
   pkm lint --root . | grep "data/style/<slug>"   # should be empty
   pkm search "<topic-keywords>" --scope style --root . -n 3   # sanity check the sample is searchable
   ```

6. **Report.** Print: imported slug, frontmatter, tags, current style corpus size (`ls data/style/*.md | wc -l`).

## Failure modes

- **WebFetch failure** → tell user to save manually, STOP. Don't fabricate body.
- **Slug collision** (`data/style/<slug>.md` already exists) → ask user to rename or pass `--force` (no force flag here yet — for now just refuse and stop).
- **Lint failure on the imported file** → fix the frontmatter and re-commit. Don't leave broken samples in the index.
