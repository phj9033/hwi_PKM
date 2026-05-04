# /blog

Outline-first blog draft from PKM, in the user's writing voice.

## Args

`/blog "<주제 또는 한 줄 요약>"` — natural-language topic. Examples: `/blog "OAuth 토큰을 안전하게 저장하기"` or `/blog "왜 monorepo 를 도입하지 않았나"`.

## Steps

1. **Retrieval (parallel).** Run all three:

   ```bash
   pkm search "<주제>" --scope wiki    -n 5 --json --root .
   pkm search "<주제>" --scope raw     -n 5 --json --root .
   pkm search "<주제>" --scope style   -n 3 --json --root .
   ```

   Read every returned `path` (Read tool, full body).

2. **Cold-start check.** If `pkm search ... --scope style` returns 0 hits AND `data/style/` is empty, print: `스타일 샘플이 없어 중립적인 한국어 블로그 톤으로 진행합니다. /style-import 로 샘플을 추가할 수 있어요.` Continue with neutral tone.

3. **Outline.** Compose and show the user:

   - **제목 후보** (3개)
   - **도입부** (2-3 문장 — 후크/맥락)
   - **본문 섹션** (3-5개): 각 섹션은 (제목, 핵심 메시지 1줄, 인용 후보 paths from wiki/raw)
   - **마무리** (다음 행동 / 메시지 / 관련 글 후보)
   - **예상 길이** (문단 수 또는 단어 수 추정)

   Wait for user approval / edits to the outline.

4. **Draft.** With user-approved outline:

   - Match the *tone, sentence length, paragraph density, and headline conventions* of the retrieved style samples (top-3 from `--scope style`). Do NOT copy phrasing — match cadence and structure.
   - Each section follows the outline's 핵심 메시지 + draws facts/examples from cited wiki/raw paths.
   - **Citation contract:** at the end of the post, add `## 참고 / Sources` listing every wiki/raw path used + any external URLs from style samples' `source_url`. Format:

     ```markdown
     ## 참고 / Sources
     - [OAuth 토큰 저장](data/wiki/concepts/oauth-token-storage.md)
     - [API 키 회전](data/wiki/concepts/api-key-rotation.md)
     - https://example.com/blog/external-ref
     ```

   - Do NOT use inline `[<path>]` citations — block-end list only (블로그는 narrative 우선).

5. **Write the draft.**

   ```
   blog/<slug>.md
   ```

   `<slug>` derived from the chosen title (lowercase, hyphen-separated, ASCII-friendly fallback for Korean — e.g. 제목이 한국어면 사용자에게 영문 slug 제안). The file has NO frontmatter — `blog/` is not indexed and not lint'd.

6. **Commit.**

   ```bash
   git add blog/<slug>.md
   git commit -m "blog: draft <slug>"
   ```

7. **Hand off.** Tell the user: file path, word count estimate, and recommendation to read + revise. Do NOT auto-publish — `blog/` is a local archive.

## Constraints

- **No external web search.** `/blog` uses only `data/wiki/`, `data/raw/`, `data/style/`. If the user wants external refs, they must add them in their revision pass.
- **No inline `[<path>]` citations.** End-of-post `## 참고` only.
- **No `--purpose` argument.** This is a sibling of `/write`, not a special case of it. `data/writing/` is for wiki-bound artifacts; `blog/` is for external publication.

## Refinement

After draft is written, the user can ask Claude in the same session to revise sections, change tone, shorten/lengthen, swap citations, etc. — those are direct Edit operations on `blog/<slug>.md`. No new slash needed.
