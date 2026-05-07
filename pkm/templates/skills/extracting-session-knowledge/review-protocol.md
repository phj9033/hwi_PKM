# Review Protocol — 2-Round User Approval

The user reviews extracted candidates in a markdown table. They respond in natural language; you parse and apply.

## Format (round 1)

```
## decisions (3)
1. **OAuth refresh in cookie** — `httpOnly` + `Secure` + `SameSite=Strict`. _Rationale:_ XSS resistance.
2. **Drop V1 API by Q3** — < 0.1% traffic, security review blocked.
3. **Use Redis for session store, not in-memory** — multi-instance deploys.

## pitfalls (1)
1. **Don't await inside `async with session:`** — `__aexit__` commits.

## snippets (2)
1. **Map user to org** (`sql`) — LATERAL JOIN to handle nullable orgs.
2. **List stale feature flags** (`bash`) — `grep -r FF_ src/ | ...`.

## qna (1)
1. Q: "Why isn't RLS working?" / A: Policy used `user_id` not `auth.uid()`.

## notes (0)
```

After table:

> "위 19 후보 검토 후 변경/제외할 것 알려주세요 (예: '`decisions 2` 빼고, `snippets 1` 의 제목 'org-mapping query' 으로 바꿔'). 다 OK 면 '진행'."

## Round 2 (after user edits)

Apply edits, show the revised list, then:

> "최종 OK?"

If user OK → proceed to write. If user has more edits → another round (max 3).

## Auto-approval mode

If the slash command was invoked with `--auto-approve` (e.g., `/pkm-extract-session abc123 --auto-approve`), skip round 1 and round 2; write all candidates as-is. Only use this mode when explicitly requested.

## Edits parser hints

The user typically says things like:
- "decisions 3 빼" → drop item 3 from decisions
- "snippets 1 제목 X 로" → rename item 1 to X
- "pitfalls 모두 빼" → drop all pitfalls
- "전부 OK" → proceed
- "진행" / "go" → proceed

When ambiguous, ask one clarifying question, then proceed.
