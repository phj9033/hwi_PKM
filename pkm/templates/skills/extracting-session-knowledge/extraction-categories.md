# Extraction Categories

What counts as each of the 5 categories. Use these definitions when building candidates.

## decisions/

A choice made among alternatives, with rationale.

**Examples:**
- "Use httpOnly cookies for refresh tokens (rationale: XSS resistance)."
- "Drop the legacy V1 endpoint after Q3 (rationale: < 0.1% traffic, security review pending)."

**Not a decision:**
- General knowledge ("CSRF tokens prevent CSRF") → `notes/` or general wiki, not project decisions.
- Code snippet without rationale → `snippets/`.

## pitfalls/

A specific gotcha encountered and the lesson learned.

**Examples:**
- "Don't `await session.commit()` inside `async with session:` — already commits on exit."
- "Migration 0042 hangs if applied during peak traffic; coordinate with ops."

**Not a pitfall:**
- General best practice ("validate inputs") → wiki concepts.
- Decision to use X instead of Y → `decisions/`.

## snippets/

Reusable code or command. Must include the language and the actual code/command.

**Examples:**
- A SQL query that maps users to their org with the correct LATERAL JOIN.
- A bash one-liner to grep for stale flags.

## qna/

A specific question + answer pair. The Q must be unique enough to be searchable.

**Examples:**
- Q: "왜 RLS 가 작동 안 하지?" / A: "...because the policy targets `user_id` not `auth.uid()`."

**Not a qna:**
- Generic Q&A like "what is X" — those go to wiki concepts.

## notes/

Anything worth keeping that doesn't fit the four above. Use sparingly — if everything ends up in notes, you're under-categorizing.
