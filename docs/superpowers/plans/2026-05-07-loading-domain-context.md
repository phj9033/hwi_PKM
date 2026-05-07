# `loading-domain-context` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a user-level Claude Code skill `loading-domain-context` that triggers before `superpowers:brainstorming` to load/establish project domain context (CONTEXT.md / CONTEXT-MAP.md), grills the user grill-with-docs style, and hands off to brainstorming.

**Architecture:** Four-file skill under `~/.claude/skills/loading-domain-context/` (SKILL.md + 3 reference docs). Per-project alias registry lives in `<project>/CLAUDE.md` under `## Agent skills` → `### Domain docs`. No code, no runtime dependencies — content is markdown only. Verification is manual scenario-based per spec §Testing.

**Tech Stack:** Markdown only. Follows mattpocock/skills `grill-with-docs` format conventions.

**Spec:** `docs/superpowers/specs/2026-05-07-loading-domain-context-design.md`

**Notes:**
- Skill folder (`~/.claude/skills/loading-domain-context/`) is not a git repo — no per-file commits there. The plan + spec are committed in this repo (`hwi_PKM`) as the canonical record.
- Reviewers and executors should treat the spec as authoritative for content; this plan is the build sequence.

---

## File Structure

| Path | Responsibility | Action |
|---|---|---|
| `~/.claude/skills/loading-domain-context/SKILL.md` | Frontmatter trigger + main flow + handoff. The skill body Claude reads on activation. | Create |
| `~/.claude/skills/loading-domain-context/CONTEXT-FORMAT.md` | Defines `CONTEXT.md` format (mattpocock port). Referenced from SKILL.md. | Create |
| `~/.claude/skills/loading-domain-context/CONTEXT-MAP-FORMAT.md` | Defines `CONTEXT-MAP.md` format for multi-context repos. Referenced from SKILL.md. | Create |
| `~/.claude/skills/loading-domain-context/BOOTSTRAP.md` | Detailed first-time bootstrap procedure. Referenced from SKILL.md. | Create |

SKILL.md is intentionally short — it owns the trigger description and orchestration. The three reference docs hold format details and bootstrap procedure so the body stays compact and the handoff instruction at the end stays salient.

---

### Task 1: Create skill directory and scaffold

**Files:**
- Create dir: `~/.claude/skills/loading-domain-context/`

- [ ] **Step 1: Verify parent dir exists**

```bash
ls ~/.claude/skills/
```
Expected: lists existing user skills (folder exists per spec §Architecture).

- [ ] **Step 2: Create skill subfolder**

```bash
mkdir -p ~/.claude/skills/loading-domain-context
ls ~/.claude/skills/loading-domain-context/
```
Expected: directory exists, empty.

---

### Task 2: Author `CONTEXT-FORMAT.md`

**Files:**
- Create: `~/.claude/skills/loading-domain-context/CONTEXT-FORMAT.md`

This is a port of `mattpocock/skills/skills/engineering/grill-with-docs/CONTEXT-FORMAT.md` plus a language-policy line. No deviations from mattpocock's format itself.

- [ ] **Step 1: Write the file**

Content must include:
- A `# CONTEXT.md Format` title and short framing paragraph
- A `## Structure` section showing the canonical template:
  - Title `# {Context Name}` + 1-2 sentence framing
  - `## Language` with at least 3 example terms in `**Term**:` / definition / `_Avoid_:` aliases shape
  - `## Relationships` with bullet list using bold term names and explicit cardinality verbs
  - `## Example dialogue` showing dev ↔ domain expert exchange that uses the bold terms
  - `## Flagged ambiguities` showing one resolved overlapping term
- A `## Rules` section with these bullets verbatim (text may be lightly rephrased but each rule must be present):
  - Be opinionated; pick one canonical word, list others as `_Avoid_:`
  - Flag conflicts explicitly under "Flagged ambiguities"
  - One-sentence definitions; define what it IS, not what it does
  - Show relationships with bold term names + cardinality
  - Domain-only — no general programming concepts
  - Group under subheadings only when natural clusters emerge
  - Always write an example dialogue
- A `## Single vs multi-context repos` section explaining single-`CONTEXT.md` vs multi-context with `CONTEXT-MAP.md`, plus the inference rules:
  - `CONTEXT-MAP.md` exists → multi
  - Only root `CONTEXT.md` → single
  - Neither → lazy-create root on first term resolution
- A `## Document language` section (this is the addition over mattpocock):
  > "Write `CONTEXT.md` in the dominant language of the project's aliased domain documents (e.g. Korean if `SCHEMA.md` is Korean, English otherwise). If aliases are mixed or empty, ask the user once during the first grill round."

- [ ] **Step 2: Verify against spec §Format Files / CONTEXT-FORMAT.md**

```bash
grep -E '^## (Structure|Rules|Single vs multi-context repos|Document language)' ~/.claude/skills/loading-domain-context/CONTEXT-FORMAT.md
```
Expected: 4 matching headings.

- [ ] **Step 3: Verify rules coverage**

```bash
grep -ciE '(opinionated|flagged ambiguities|one[- ]sentence|domain-only|example dialogue)' ~/.claude/skills/loading-domain-context/CONTEXT-FORMAT.md
```
Expected: count ≥ 5 (each rule keyword present at least once).

---

### Task 3: Author `CONTEXT-MAP-FORMAT.md`

**Files:**
- Create: `~/.claude/skills/loading-domain-context/CONTEXT-MAP-FORMAT.md`

Port of `mattpocock/skills/skills/engineering/grill-with-docs/SKILL.md` multi-context section + small example. No new behavior — purely the format reference.

- [ ] **Step 1: Write the file**

Content must include:
- `# CONTEXT-MAP.md Format` title + 1-paragraph purpose
- A `## Template` block showing:
  - `# Context Map`
  - `## Contexts` bullet list with format `[Name](./path/to/CONTEXT.md) — one-line description`
  - `## Relationships` bullets with format `**A → B**: A emits X events; B consumes them to do Y` and shared types like `**A ↔ B**: Shared types for ...`
- A `## When this file applies` section stating the inference rules (mirroring CONTEXT-FORMAT §Single vs multi-context repos), so the file is self-contained.
- A `## Per-context CONTEXT.md` paragraph clarifying that each context listed in the map gets its own `CONTEXT.md` at the listed path, written using the format in `CONTEXT-FORMAT.md`.

- [ ] **Step 2: Verify required sections present**

```bash
grep -E '^## (Template|When this file applies|Per-context CONTEXT\.md)' ~/.claude/skills/loading-domain-context/CONTEXT-MAP-FORMAT.md
```
Expected: 3 matching headings.

---

### Task 4: Author `BOOTSTRAP.md`

**Files:**
- Create: `~/.claude/skills/loading-domain-context/BOOTSTRAP.md`

This is the longest reference file because it contains operational steps. Spec §Format Files / BOOTSTRAP.md and §Edge Cases together fully define behavior.

- [ ] **Step 1: Write the file**

Content must cover the four phases from spec verbatim in intent:

**1. Candidate scan**
- Patterns: `CONTEXT*.md`, `CONTEXT-MAP*.md`, `SCHEMA*.md`, `FEATURES*.md`, `glossary*.md`, `GLOSSARY*.md`, `domain*.md`, `ontology*.md`, `terms*.md`, `README.md`
- Rules: case-insensitive filename match; depth 1–2 from project root; skip `node_modules/`, `.git/`, `dist/`, `build/`; do not follow symlinks; only regular files ending in `.md`; if pattern resolves to a directory or non-`.md` file, skip silently
- Suggested command shape (so the executor agent uses a deterministic search):
  ```bash
  find . -maxdepth 2 -type f -iname '<pattern>.md' \
    -not -path './node_modules/*' -not -path './.git/*' \
    -not -path './dist/*' -not -path './build/*'
  ```

**2. Presentation format** (one assistant message, not multiple):
```
감지된 도메인 문서 후보:
  [1] SCHEMA.md
  [2] FEATURES.md
  [3] README.md

응답해줘:
  - 등록할 번호 (예: "1,2")
  - 추가할 경로 ("path: docs/onto.md" 형식, 여러 줄 가능)
  - 또는 "없음" → 빈 등록부로 시작
  - 또는 "skip" → 부트스트랩 중단, 핸드오프
```

**3. CLAUDE.md write template** (exactly this, including the HTML comment marker):
```md
## Agent skills

### Domain docs
<!-- managed by loading-domain-context skill -->
- SCHEMA.md
- FEATURES.md
```

Editing rules:
- If `## Agent skills` section is absent, append the entire template at end of file with one preceding blank line
- If `## Agent skills` exists but no `### Domain docs` subsection, append the `### Domain docs` subsection at end of `## Agent skills`
- If `### Domain docs` subsection exists, replace the entire subsection (preserve subsequent sections)
- The HTML comment marker `<!-- managed by loading-domain-context skill -->` is required as the second line of the subsection — it is the parsing anchor

**4. CLAUDE.md absent flow**:
- Confirm once: "이 프로젝트엔 `CLAUDE.md`가 없음. 새로 만들고 `### Domain docs` 블록을 기록할까? (yes / no)"
- yes → create `CLAUDE.md` with just the `## Agent skills` / `### Domain docs` block
- no → abort bootstrap, hand off with no registry; document that next invocation will retry

- [ ] **Step 2: Verify required phases present**

```bash
grep -cE '^## (Candidate scan|Presentation format|CLAUDE\.md write template|CLAUDE\.md absent)' ~/.claude/skills/loading-domain-context/BOOTSTRAP.md
```
Expected: 4.

- [ ] **Step 3: Verify HTML marker is documented**

```bash
grep -F 'managed by loading-domain-context skill' ~/.claude/skills/loading-domain-context/BOOTSTRAP.md
```
Expected: at least one match (the marker text appears in the template).

---

### Task 5: Author `SKILL.md` (main file)

**Files:**
- Create: `~/.claude/skills/loading-domain-context/SKILL.md`

This is the entry point. Keep body short — references companion files for detail. Handoff block must be the last section so it stays salient.

- [ ] **Step 1: Write frontmatter (verbatim from spec §Trigger & Handoff)**

```yaml
---
name: loading-domain-context
description: Use BEFORE superpowers:brainstorming whenever creative work begins — features, components, functionality, or behavior changes. Loads project domain context from CLAUDE.md aliases (CONTEXT.md, CONTEXT-MAP.md, or user-registered docs), grills user to resolve terminology and ambiguities relevant to the upcoming work, then hands off to brainstorming.
---
```

- [ ] **Step 2: Write body**

Body must include these sections in order:

**`# Loading Domain Context`** — 2-sentence framing: prerequisite to brainstorming; loads/registers domain docs and resolves terminology before brainstorming starts.

**`## When to run`** — explicit list of trigger conditions (creative work, features, components, behavior changes). One bullet stating: "If user explicitly invokes `/superpowers:brainstorming` directly, this skill is bypassed — that is intended."

**`## Main flow`** — copy the ASCII flow from spec §SKILL.md Main Flow:
- [1] State detection (check `CLAUDE.md` for `## Agent skills` → `### Domain docs` block; presence of HTML marker is required for "registered" state)
- [2] Bootstrap (one-line summary + reference: "See `BOOTSTRAP.md` for full procedure")
- [3] Runtime (one-line summary of: read aliases, multi-context inference, grill loop with one-question-per-message, mattpocock principles — challenge terminology, sharpen fuzzy terms, cross-reference code, lazy-update CONTEXT.md inline; reference: "See `CONTEXT-FORMAT.md` and `CONTEXT-MAP-FORMAT.md` for output formats")
- Mark grill-loop stop as **strictly user-controlled** — model must not auto-stop on judgement of "terms clear enough"

**`## Document language`** — one paragraph: write CONTEXT.md / CONTEXT-MAP.md in the dominant language of aliased docs; ask once if mixed or empty.

**`## Edge cases`** — table mirroring spec §Edge Cases (7 rows). Keep concise — just the row, not full prose.

**`## Handoff to brainstorming`** (must be the LAST section, and must contain this verbatim):

```md
You MUST invoke the `superpowers:brainstorming` skill via the Skill tool only when the user explicitly signals to proceed: `넘어가자` / `ok 진행` / `proceed` / `skip`. Do not auto-hand-off based on model judgement that "terms are clear enough" — the stop condition is strictly user-controlled. Do not write code, scaffold, or invoke other skills before this handoff. Brainstorming is the only allowed downstream skill.
```

- [ ] **Step 3: Verify frontmatter trigger phrase**

```bash
grep -F 'Use BEFORE superpowers:brainstorming' ~/.claude/skills/loading-domain-context/SKILL.md
```
Expected: 1 match (in the description field).

- [ ] **Step 4: Verify handoff block is last and strict**

```bash
tail -10 ~/.claude/skills/loading-domain-context/SKILL.md | grep -F 'strictly user-controlled'
```
Expected: match found.

- [ ] **Step 5: Verify reference files are linked**

```bash
grep -cE '(BOOTSTRAP\.md|CONTEXT-FORMAT\.md|CONTEXT-MAP-FORMAT\.md)' ~/.claude/skills/loading-domain-context/SKILL.md
```
Expected: 3 (each companion file referenced at least once).

---

### Task 6: Sanity-check skill folder against spec

**Files:**
- Read-only: all 4 skill files

- [ ] **Step 1: Verify all 4 files exist and are non-empty**

```bash
for f in SKILL.md CONTEXT-FORMAT.md CONTEXT-MAP-FORMAT.md BOOTSTRAP.md; do
  test -s ~/.claude/skills/loading-domain-context/$f && echo "OK: $f" || echo "MISSING/EMPTY: $f"
done
```
Expected: 4 lines all `OK: …`.

- [ ] **Step 2: Verify Skill tool can list the new skill**

In a fresh Claude Code session (or by reloading the current one's skills), confirm `loading-domain-context` appears in the available-skills list with the expected description. This is a manual check — there is no CLI flag to introspect skills.

Expected: `loading-domain-context` is listed alongside other user skills (e.g., `simplify`, `init`).

---

### Task 7: Manual test scenario 1 — empty new project

**Files:** none (uses a temp scratch directory).

- [ ] **Step 1: Create scratch project**

```bash
mkdir -p /tmp/ldc-test-empty
cd /tmp/ldc-test-empty
git init -q
```

- [ ] **Step 2: Open Claude Code in scratch dir, send creative-work prompt**

Manually: in a Claude Code session rooted at `/tmp/ldc-test-empty`, send: "Add a simple TODO list feature".

Expected: `loading-domain-context` triggers (not brainstorming first). First assistant message is the bootstrap candidate prompt with 0 candidates and the `없음 / skip` menu.

- [ ] **Step 3: Reply `없음`**

Expected: `CLAUDE.md` is created with just the `## Agent skills` → `### Domain docs` block (empty list under HTML marker). Skill then enters runtime with empty alias set, grill loop starts asking a domain-relevant question.

- [ ] **Step 4: Reply `skip`**

Expected: skill invokes `superpowers:brainstorming` immediately. Brainstorming begins its own clarifying question flow.

- [ ] **Step 5: Record outcome**

Mark scenario as PASS / FAIL in plan checklist with one-line notes (e.g., which step diverged from expectation).

---

### Task 8: Manual test scenario 2 — hwi_PKM (real first target)

**Files:** `<hwi_PKM>/CLAUDE.md` will be modified.

- [ ] **Step 1: Pre-check — verify CLAUDE.md state before test**

```bash
grep -F '### Domain docs' /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/CLAUDE.md 2>/dev/null && echo "BLOCK ALREADY EXISTS — back up and remove before testing" || echo "OK: no existing block"
```
Expected: `OK: no existing block` for first-run scenario. If block exists, save a backup and delete the block before continuing.

- [ ] **Step 2: Trigger the skill**

In a Claude Code session at hwi_PKM, send: "Let's add a new feature for note tagging".

Expected: `loading-domain-context` triggers. First assistant message lists candidates — at minimum `SCHEMA.md`, `FEATURES.md`, `README.md` (case-insensitive scan; if hwi_PKM has additional files matching patterns, those should appear too).

- [ ] **Step 3: Select `SCHEMA.md` and `FEATURES.md` (e.g., reply `1,2`)**

Expected: skill writes the `### Domain docs` block to `CLAUDE.md` listing those two files under the HTML marker. Then enters runtime, reads both files, then begins grill loop with a tagging-related domain question.

- [ ] **Step 4: Verify CLAUDE.md was modified correctly**

```bash
grep -A 5 '### Domain docs' /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/CLAUDE.md
```
Expected: HTML marker line + `- SCHEMA.md` + `- FEATURES.md`.

- [ ] **Step 5: Answer 1 grill question, then reply `넘어가자`**

Expected: skill invokes `superpowers:brainstorming`. Spec §SKILL.md states context propagates naturally — verify brainstorming's first message references the loaded domain (e.g., uses bold terms from SCHEMA/FEATURES).

- [ ] **Step 6: Record outcome**

PASS/FAIL with notes.

---

### Task 9: Manual test scenario 3 — repeat invocation + skip

**Files:** assumes `<hwi_PKM>/CLAUDE.md` already has the block from Task 8.

- [ ] **Step 1: Trigger skill again with creative prompt**

In a fresh session at hwi_PKM: "Improve the CLI status command".

Expected: bootstrap is **skipped** (block already present). First message is a grill question, not a candidate list.

- [ ] **Step 2: Reply `skip` immediately**

Expected: skill invokes `superpowers:brainstorming` with zero grill questions answered.

- [ ] **Step 3: Record outcome**

PASS/FAIL.

---

### Task 10: Manual test scenario 4 — missing alias file

**Files:** `<hwi_PKM>/SCHEMA.md` temporarily renamed.

- [ ] **Step 1: Rename SCHEMA.md to simulate missing file**

```bash
mv /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/SCHEMA.md /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/SCHEMA.md.bak
```

- [ ] **Step 2: Trigger skill with creative prompt**

Expected: skill detects `SCHEMA.md` listed in registry but missing on disk. First message is a "missing/invalid" prompt with options remove / fix path / leave.

- [ ] **Step 3: Reply `remove`**

Expected: `CLAUDE.md` block updated with `SCHEMA.md` removed; skill enters runtime with remaining aliases.

- [ ] **Step 4: Restore file**

```bash
mv /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/SCHEMA.md.bak /Users/ad03159868/Downloads/Claude_lab/hwi_PKM/SCHEMA.md
```

- [ ] **Step 5: Record outcome**

PASS/FAIL.

---

### Task 11: Manual test scenario 5 — trigger priority

**Files:** none (observation only).

- [ ] **Step 1: In a fresh session at hwi_PKM, send a bug-fix prompt**

Send: "Fix the failing test in test_migration_002_kiwi.py".

Expected (per spec §Testing #5): the very first assistant message comes from `loading-domain-context` (bootstrap candidate list OR a grill question), **not** from `superpowers:brainstorming` (which would start with "what's the purpose / constraints" framing).

- [ ] **Step 2: Record observable**

Capture the first assistant message. PASS if it matches `loading-domain-context` shape; FAIL with note if brainstorming pre-empted.

---

### Task 12: Manual test scenario 6 — free-form CONTEXT.md preservation

**Files:** `<scratch>/CONTEXT.md` (free-form).

- [ ] **Step 1: Set up scratch repo with free-form CONTEXT.md**

```bash
mkdir -p /tmp/ldc-test-freeform && cd /tmp/ldc-test-freeform && git init -q
cat > CONTEXT.md <<'EOF'
# Project context

This is a free-form description without mattpocock sections.
The project is about widgets that connect to gizmos via cables.
EOF
cat > CLAUDE.md <<'EOF'
## Agent skills

### Domain docs
<!-- managed by loading-domain-context skill -->
- CONTEXT.md
EOF
```

- [ ] **Step 2: Trigger skill, drive grill to register a new term, then `skip`**

In a Claude Code session at `/tmp/ldc-test-freeform`, send a creative-work prompt and answer the first grill question by introducing a new term (e.g., "we should add the concept of a `Bundle` — a collection of widgets shipped together").

- [ ] **Step 3: Verify CONTEXT.md was preserved + appended**

```bash
cat /tmp/ldc-test-freeform/CONTEXT.md
```
Expected:
- Original free-form text intact (untouched)
- New `## Language` section appended (or other mattpocock sections lazy-created), with `**Bundle**:` definition under it
- No reformatting of pre-existing prose

- [ ] **Step 4: Record outcome**

PASS/FAIL.

---

### Task 13: Commit plan execution log

**Files:**
- Modify: `docs/superpowers/plans/2026-05-07-loading-domain-context.md` (this file — append outcome notes)

- [ ] **Step 1: Append a `## Execution log` section to this plan with one bullet per scenario (1–6) capturing PASS/FAIL + one-line note + date.**

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-07-loading-domain-context.md
git commit -m "docs(plan): execution log for loading-domain-context skill"
```

---

## Risks / Things to watch during execution

- **Trigger priority is observational, not guaranteed.** Task 11 may fail if Claude's skill matcher ranks `superpowers:brainstorming` higher despite our more-specific description. Fallback: strengthen description with the literal phrase "before brainstorming" in multiple positions, or add an explicit user-level CLAUDE.md hint.
- **CLAUDE.md write template parsing** must be implemented in a way that survives free-form sections elsewhere in the file. The HTML comment marker is the parsing anchor — if it gets stripped, parsing must fail closed (re-bootstrap), not silently overwrite content.
- **First grill question quality** depends on the model — there is no deterministic test for it. Manual judgment during Task 8.
- **Skill body length** (Task 5) — keep SKILL.md under ~150 lines so the handoff section stays in the model's "recent" window. If it grows, push more detail into BOOTSTRAP.md / format files.

## References

- Spec: `docs/superpowers/specs/2026-05-07-loading-domain-context-design.md`
- Source pattern: `mattpocock/skills/skills/engineering/grill-with-docs/`
- Brainstorming skill (downstream handoff target): `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.5/skills/brainstorming/SKILL.md`
