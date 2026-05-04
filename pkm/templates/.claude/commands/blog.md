# /blog

Outline-first blog draft from PKM, in the user's writing voice. Two modes:

- **Topic mode** — `/blog "<주제>"`: search wiki/raw/style → outline → draft from a user-specified topic.
- **Random mode** — `/blog --random`: serendipity drafts from random wiki cards (3-5장, link distance ≥ 2). Output → `blog/seeds/<slug>.md`.

## Args

- `/blog "<주제 또는 한 줄 요약>"` — natural-language topic. Examples: `/blog "OAuth 토큰을 안전하게 저장하기"` or `/blog "왜 monorepo 를 도입하지 않았나"`.
- `/blog --random` — serendipity mode. No topic; sample 3-5 random wiki cards with no two directly linked. Output goes to `blog/seeds/<slug>.md`.

## Steps

### Mode dispatch

Look at the args:

- If args contain the literal token `--random`: go to **Random mode** (R1 onwards).
- Else: go to **Topic mode** (T1 onwards) with the args as the topic string.

---

### Topic mode

**T1. Retrieval (parallel).** Run all three:

```bash
pkm search "<주제>" --scope wiki    -n 5 --json --root .
pkm search "<주제>" --scope raw     -n 5 --json --root .
pkm search "<주제>" --scope style   -n 3 --json --root .
```

Read every returned `path` (Read tool, full body).

**T2. Cold-start check.** If `pkm search ... --scope style` returns 0 hits AND `data/style/` is empty, print: `스타일 샘플이 없어 중립적인 한국어 블로그 톤으로 진행합니다. /style-import 로 샘플을 추가할 수 있어요.` Continue with neutral tone.

**T3. Outline.** Compose and show the user:

- **제목 후보** (3개)
- **도입부** (2-3 문장 — 후크/맥락)
- **본문 섹션** (3-5개): 각 섹션은 (제목, 핵심 메시지 1줄, 인용 후보 paths from wiki/raw)
- **마무리** (다음 행동 / 메시지 / 관련 글 후보)
- **예상 길이** (문단 수 또는 단어 수 추정)

Wait for user approval / edits to the outline.

**T4. Draft.** With user-approved outline:

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

**T5. Write the draft.**

```
blog/<slug>.md
```

`<slug>` derived from the chosen title (lowercase, hyphen-separated, ASCII-friendly fallback for Korean — e.g. 제목이 한국어면 사용자에게 영문 slug 제안). The file has NO frontmatter — `blog/` is not indexed and not lint'd.

**T6. Commit.**

```bash
git add blog/<slug>.md
git commit -m "blog: draft <slug>"
```

**T7. Hand off.** Tell the user: file path, word count estimate, and recommendation to read + revise. Do NOT auto-publish — `blog/` is a local archive.

---

### Random mode (when args contain `--random`)

**R1. Sample.**

```bash
pkm sample --json --root .
```

Read JSON: `{"ok": true, "paths": [...], "n": N, "constraint_relaxed": bool}`. If `ok: false`, surface error to user and stop:

```
랜덤 샘플링 실패: <error.code> — <error.message>
hint: <error.hint>
```

If `constraint_relaxed: true`, prepend this note when showing the outline in R3:
> 참고: wiki 카드들이 너무 촘촘히 연결되어 있어 링크 거리 제약을 완화하고 뽑았습니다.

Read every returned `path` (Read tool, full body).

**R2. Style retrieval.** Glob `data/style/*.md` (Bash: `ls data/style/*.md 2>/dev/null` or Glob tool). Read each. If empty, print: `스타일 샘플이 없어 중립적인 한국어 블로그 톤으로 진행합니다. /style-import 로 샘플을 추가할 수 있어요.` Continue with neutral tone.

**R3. Outline.** Compose and show the user (same shape as Topic mode):

- **제목 후보** (3개) — angles that unify the random cards
- **도입부** (2-3 문장)
- **본문 섹션** (3-5개): 각 섹션 (제목, 핵심 메시지 1줄, 인용 후보 paths from sampled wiki cards)
- **마무리**
- **예상 길이**

Wait for user approval / edits to the outline. If the user wants different cards, they re-run `/blog --random`.

**R4. Draft.** Same as Topic mode T4 (tone-match style samples, end-of-post `## 참고 / Sources` listing the sampled wiki paths). No external URLs in random mode.

**R5. Write the draft.**

```
blog/seeds/<slug>.md
```

Create `blog/seeds/` directory if missing. `<slug>` derived from the chosen title, same convention as Topic mode. No frontmatter.

**R6. Commit.**

```bash
mkdir -p blog/seeds
git add blog/seeds/<slug>.md
git commit -m "blog: seed draft <slug>"
```

**R7. Hand off.** Tell the user: "랜덤 시드 초안 — 영감 카드함에 추가됨. 마음에 들면 `/blog \"<주제>\"` 로 정규 글을 다시 쓰거나 직접 다듬어 `blog/` 로 옮기세요." + file path + word count.

---

## Constraints

- **No external web search.** `/blog` uses only `data/wiki/`, `data/raw/`, `data/style/`. If the user wants external refs, they must add them in their revision pass.
- **Random mode** uses only sampled wiki cards (no `pkm search`) for content, plus all of `data/style/` for tone. No external refs.
- **No inline `[<path>]` citations.** End-of-post `## 참고` only.
- **No `--purpose` argument.** This is a sibling of `/write`, not a special case of it. `data/writing/` is for wiki-bound artifacts; `blog/` is for external publication.

## Refinement

After draft is written, the user can ask Claude in the same session to revise sections, change tone, shorten/lengthen, swap citations, etc. — those are direct Edit operations on `blog/<slug>.md` (Topic mode) or `blog/seeds/<slug>.md` (Random mode). No new slash needed.
