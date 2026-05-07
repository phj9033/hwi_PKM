# /style-import

Index and verify an already-prepared style sample at `data/style/<slug>.md` so `/blog` can use it as a tone reference.

> 본문 수집·정제·프론트매터 작성은 이 커맨드의 책임이 아닙니다. `data/style/<slug>.md` 가 이미 존재한다고 가정합니다.

## Args

`/style-import <slug>` — slug must match an existing file at `data/style/<slug>.md`.

## Steps

1. **Precheck.** Confirm `data/style/<slug>.md` exists. If missing, tell the user: "`data/style/<slug>.md` 가 없습니다. 샘플 파일을 먼저 준비한 뒤 다시 호출해주세요." and STOP.

2. **Reindex + commit.**

   ```bash
   pkm reindex db --scope style --root .
   git add data/style/<slug>.md
   git commit -m "style: import <slug>"
   ```

3. **Verify.**

   ```bash
   pkm lint --root . | grep "data/style/<slug>"   # should be empty
   pkm search "<topic-keywords>" --scope style --root . -n 3   # sanity check the sample is searchable
   ```

4. **Report.** Print: indexed slug, current style corpus size (`ls data/style/*.md | wc -l`), and the top search hit from step 3.

## Failure modes

- **Missing file** (`data/style/<slug>.md` not found) → instruct user to prepare it first, STOP.
- **Lint failure on the imported file** → fix the frontmatter and re-commit. Don't leave broken samples in the index.
- **Search returns 0 hits after reindex** → reindex likely failed or frontmatter is malformed. Re-run lint and reindex before reporting success.
