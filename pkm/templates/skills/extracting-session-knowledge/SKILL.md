---
name: pkm:extracting-session-knowledge
description: Use when user wants to harvest knowledge from a Claude Code session (e.g., "정리해줘", "이 세션에서 배운 거 저장하자", "끝!"), or signals work is complete in a linked PKM project. Reads transcript, produces 5-category candidates, reviews with user, writes to data/projects/<id>/.
---

# pkm:extracting-session-knowledge

Turns an AI conversation into permanent project knowledge. Two-round user review gate — extracts everything that could matter, then narrows by user feedback.

## When to use

- User explicitly asks to extract: "정리해줘", "save this session", "extract knowledge".
- User signals end-of-work: "끝", "그럼 이걸로 마무리", "all done", and the cwd is a linked PKM project.

## Prerequisites (the skill checks these)

- `pkm project current` resolves to a project (NOT_LINKED → tell user to `pkm project link` first).
- A session uuid is available (env `CLAUDE_SESSION_ID`, user-provided arg, or fallback to most recent today's session).

## Steps

### 1. Resolve session uuid

Priority:
1. If user passed an arg (e.g., `/pkm-extract-session abc123`) → use that.
2. Else read env var `CLAUDE_SESSION_ID` (Claude Code exposes this).
3. Else `pkm session list --project $(pkm project current) --json --limit 1` → take the most recent.
4. Else: tell user "현재 세션 식별 불가. uuid 인자로 명시해주세요" and stop.

### 2. Get transcript path

```bash
pkm session show <uuid> --json
```

If `code: NOT_LINKED` → "이 세션의 cwd 는 link 안 됨. `pkm project link` 먼저 실행 권장" — stop.

Note `transcript_path` and `project_id` from output.

### 3. Read transcript

Use the `Read` tool on `transcript_path`.

If transcript is very long (> ~5000 lines or token limit risk):
- Process in 50-message windows with 5-message overlap.
- Accumulate candidates per category, deduplicate at the end.

If `Read` raises (corrupt jsonl) → tell user, stop.

### 4. Build candidates

Read `extraction-categories.md` to know what counts as each of the 5 categories. Read `output-schema.md` for the exact JSON shape.

For each category, list candidates with: `title`, `summary` (3-4 sentences max), `tags`, optional `code` (snippets), `derived_from` (cite turns or files referenced).

Be inclusive — if it's borderline, include it. The review gate (step 5) trims.

### 5. Review (round 1)

Present all candidates as a single Markdown table grouped by category. See `review-protocol.md` for the format. Then ask:

> "위 후보들 중 변경/제외할 것 알려주세요 (예: 'decisions 3 빼고, snippets 2 의 제목 OAuth refresh으로 바꿔줘'). 다 OK 면 '진행'."

### 6. Apply user feedback + Review (round 2)

Apply edits, present revised list. Ask:

> "최종 OK?"

If user says no → another round (max 3 rounds; then ask for explicit list).

### 7. Write files

For each accepted candidate:

```bash
echo '<body>' | pkm project knowledge add \
  --project <project_id> \
  --category <category> \
  --slug <user-friendly-slug> \
  --title '<title>' \
  --tags '<tags-comma-sep>' \
  --source-type ai_session \
  --session-id <uuid> \
  --json
```

Capture each `path` returned in JSON.

### 8. Mark processed

```bash
pkm session mark-processed <uuid> --extracted-count <total>
```

### 9. Rebuild + reindex

```bash
pkm project rebuild-index <project_id>
pkm reindex db --scope project:<project_id>
```

### 10. Report

> "Extraction complete. <project_id>: decisions N, pitfalls M, snippets K, qna L, notes O. New items in `data/projects/<project_id>/`. Run `/pkm-recall <topic>` next time to retrieve."

## Portability rules

- Use `pkm project current` and `pkm session show` for all path/id resolution. Never hardcode.
- All file writes go through `pkm project knowledge add`. Do NOT use `Edit`/`Write` directly on `data/projects/**`.
- Single retry on `pkm project knowledge add` failure (e.g., transient git auto-commit conflict). Surface user-facing errors verbatim.
