# /style-import

Index and verify an already-prepared style sample at `data/style/<style>/<sample>.md` so `/blog` can use it as a tone reference.

> 본문 수집·정제·프론트매터 작성은 이 커맨드의 책임이 아닙니다. 샘플 파일이 이미 존재한다고 가정합니다.

## Args

`/style-import <style>/<sample>` — both segments lowercase, hyphen-separated. The file must already exist at `data/style/<style>/<sample>.md`.

## Steps

1. **Precheck.** Confirm `data/style/<style>/<sample>.md` exists. If missing, tell the user: "`data/style/<style>/<sample>.md` 가 없습니다. 샘플 파일을 먼저 준비한 뒤 다시 호출해주세요." and STOP.

2. **Reindex + commit.**

   ```bash
   pkm reindex db --scope style --root .
   git add data/style/<style>/<sample>.md
   git commit -m "style: import <style>/<sample>"
   ```

3. **Verify.**

   ```bash
   pkm lint --root . | grep "data/style/<style>/<sample>"   # should be empty
   pkm search "<topic-keywords>" --scope style --root . -n 3   # sanity check the sample is searchable
   ```

4. **Report.** Print: indexed `<style>/<sample>`, sample count for the style (`ls data/style/<style>/*.md | wc -l`), total style count (`ls -d data/style/*/ | wc -l`), and the top search hit from step 3.

## Failure modes

- **Missing file** (`data/style/<style>/<sample>.md` not found) → instruct user to prepare it first, STOP.
- **Flat file** (`data/style/<sample>.md` without a style directory) → lint will surface `STYLE_FLAT_FILE`. Move it under a style directory and re-run.
- **Lint failure** on the imported file → fix the frontmatter and re-commit.
- **Search returns 0 hits after reindex** → reindex likely failed or frontmatter is malformed. Re-run lint and reindex before reporting success.
