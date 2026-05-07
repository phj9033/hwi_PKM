---
name: pkm:backfilling-sessions
description: Use when user wants to process historical Claude Code sessions in bulk to seed project knowledge ("과거 세션 다 정리하자", "backfill", "분석해서 등록"). Resumable — interrupted backfill picks up from last completed session.
---

# pkm:backfilling-sessions

Bulk-extract knowledge from past Claude Code sessions. Idempotent + resumable: interrupted backfills resume from the last completed session.

## When to use

- User says "이 프로젝트 과거 세션 다 정리해줘" or "/pkm-backfill".
- First time setting up PKM and wanting to seed from existing transcript history.

## Prerequisites

- `pkm project current` or explicit `--project` arg.
- At least one session in `~/.claude/projects/**/*.jsonl` for the target project.

## Steps

### 1. Discover unprocessed sessions

```bash
pkm session list --unprocessed --json [--project <id>] [--since <date>] [--min-messages 5]
```

The `--min-messages 5` default skips trivial sessions. Adjust if user requests.

If 0 sessions → "처리할 세션 없음. 모두 이미 처리됨." Stop.

### 2. Confirm with user

> "<N> 세션 처리 예정 (총 <total_messages> 메시지). 첫 세션은 자세히 검토, 이후는 일괄 모드 가능. 진행?"

Wait for "진행" / "ok" / "go".

Ask separately:

> "첫 세션 검토 후 일괄 모드로 전환할까요? (yes/no)"

### 3. For each session (oldest → newest)

For session i in 1..N:

a. Get transcript: `pkm session show <uuid> --json` → `transcript_path`, `project_id`.

b. Read transcript via `Read` tool. Window if long (50 messages, overlap 5).

c. **First session OR per-session mode**:
   - Run the full `pkm:extracting-session-knowledge` two-round review.
   - After completion, ask: "다음 세션도 같은 방식? 아니면 일괄 모드?"

   **Batch mode after first session**:
   - Build candidates with same logic.
   - Show single round of candidates.
   - Ask "이 세션 일괄 진행 OK? (yes/skip-this/edit/stop-batch)"
   - On `yes` → write directly + mark processed + continue.
   - On `skip-this` → don't write, but mark as processed (so future backfills skip it).
   - On `edit` → drop into round-2 review for this session, then continue batch.
   - On `stop-batch` → exit loop, leave remaining sessions unprocessed.

d. **Crash safety**: if any step in (a)-(c) fails (transcript corrupt, mark-processed errors), do NOT mark processed. The next backfill run will re-attempt.

### 4. After loop

```bash
pkm project rebuild-index <project_id>
pkm reindex db --scope project:<project_id>
```

Report:

> "Backfill complete: <N_processed>/<N_total> sessions, <total_items> items added (decisions <a>, pitfalls <b>, snippets <c>, qna <d>, notes <e>). 검토 미완 항목은 `pkm project show <project_id>` 에서 status=draft 로 확인."

## Resumability

- Each session's mark-processed call writes `.pkm/sessions/<project>/<uuid>.json`.
- Next `pkm session list --unprocessed` automatically excludes processed sessions.
- If user wants to re-process a specific session: `pkm session forget <uuid>` then re-run backfill.

## Cost guardrails

- Long transcripts (>5000 lines) — warn user and process in windows.
- If user has 100+ sessions, suggest `--since` filter to scope.
- Token budget: track approximate per-session and warn if approaching limits.

## Portability rules

Same as `pkm:extracting-session-knowledge`. Always use `pkm` CLI for paths/ids.
