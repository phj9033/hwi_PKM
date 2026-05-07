# `loading-domain-context` Skill — Design Spec

- **Date:** 2026-05-07
- **Status:** Draft (post-brainstorming)
- **Author:** hwi (with Claude)
- **Scope:** New user-level Claude Code skill that runs before `superpowers:brainstorming` to load or establish project domain context.

## Goal

Provide a project-agnostic, reusable skill that:

1. Loads existing project domain documents (or registers them via alias) before any creative work begins.
2. Grills the user against those documents to resolve terminology and ambiguities relevant to the upcoming brainstorming topic.
3. Updates the canonical `CONTEXT.md` / `CONTEXT-MAP.md` inline as decisions emerge.
4. Hands off cleanly to `superpowers:brainstorming` so brainstorming starts with shared domain language already loaded.

The skill is inspired by `mattpocock/skills` — specifically `grill-with-docs` — but excludes the ADR component to keep the per-brainstorming overhead bounded.

## Non-goals

- ADR creation/management (deferred; may become a separate `recording-adr` skill later).
- Issue tracker setup, triage labels, PRD generation (mattpocock's `setup-matt-pocock-skills` / `to-prd` / `triage` scope).
- Modifying or replacing `superpowers:brainstorming` itself. The plugin-cached `SKILL.md` is treated as immutable.
- Cross-assistant compatibility (Codex, Gemini CLI). Claude Code only.

## Background

`superpowers:brainstorming` triggers on any creative work but starts from a blank context. For projects with existing terminology (`SCHEMA.md`, `FEATURES.md`, glossaries), this means brainstorming repeatedly re-discovers domain language and risks drifting from established terms. `mattpocock/skills` solves this with a `CONTEXT.md` shared-vocabulary file plus a `grill-with-docs` interview skill, but their skill is invoked manually and isn't wired into a brainstorming-first workflow.

This spec wires the same pattern in as a *prerequisite* skill that triggers before brainstorming.

## Architecture

### Install location

```
~/.claude/skills/loading-domain-context/
├── SKILL.md
├── CONTEXT-FORMAT.md
├── CONTEXT-MAP-FORMAT.md
└── BOOTSTRAP.md
```

User-level skill (applies to all projects). No plugin wrapping.

### Project-side artifacts (touched at runtime)

| File | Role | Lifecycle |
|---|---|---|
| `<project>/CLAUDE.md` | Holds the `## Agent skills` → `### Domain docs` alias registry | Read on every run; written during bootstrap or when registry changes |
| `<project>/CONTEXT.md` (single context) | Canonical domain glossary | Lazy created when first term resolved |
| `<project>/CONTEXT-MAP.md` (multi-context) | Index of per-context `CONTEXT.md` files | Lazy created when multi-context inferred |
| User-aliased docs (e.g. `SCHEMA.md`, `FEATURES.md`) | Pre-existing domain docs read as-is | Skill never reformats them |

### External dependencies

None at runtime. Format files are bundled in the skill folder; mattpocock's repo is referenced only as the design source.

## Trigger & Handoff Mechanics

### Frontmatter

```yaml
---
name: loading-domain-context
description: Use BEFORE superpowers:brainstorming whenever creative work begins — features, components, functionality, or behavior changes. Loads project domain context from CLAUDE.md aliases (CONTEXT.md, CONTEXT-MAP.md, or user-registered docs), grills user to resolve terminology and ambiguities relevant to the upcoming work, then hands off to brainstorming.
---
```

The `Use BEFORE superpowers:brainstorming` clause is the priority signal. Both this skill and brainstorming are process skills under the using-superpowers ranking; ours is more specific because it names brainstorming as the next step, so it matches first when both are candidates.

### Handoff

`SKILL.md` ends with a fixed handoff block:

```md
## Handoff to brainstorming

You MUST invoke the `superpowers:brainstorming` skill via the Skill tool only when the user explicitly signals to proceed: `넘어가자` / `ok 진행` / `proceed` / `skip`. Do not auto-hand-off based on model judgement that "terms are clear enough" — the stop condition is strictly user-controlled. Do not write code, scaffold, or invoke other skills before this handoff. Brainstorming is the only allowed downstream skill.
```

The skill never writes code, scaffolds, or invokes any other skill. Brainstorming is the only allowed downstream skill.

### Skip

`skip` / `넘어가자` is honored anywhere — during bootstrap candidate selection, during the grill loop, or as the very first input. Skipping during bootstrap leaves no `### Domain docs` block, so the next invocation re-attempts bootstrap.

### Explicit user invocation of brainstorming

If the user types `/superpowers:brainstorming` directly, this skill is bypassed. Treated as deliberate user choice; no special handling.

## SKILL.md Main Flow

```
[1] State detection
    └─ <project>/CLAUDE.md has "## Agent skills" → "### Domain docs" block?
        ├─ no  → [2] Bootstrap
        └─ yes → [3] Runtime

[2] Bootstrap (details: BOOTSTRAP.md)
    ├─ Auto-scan candidate files at depth 1–2:
    │   CONTEXT*.md, CONTEXT-MAP*.md, SCHEMA*.md, FEATURES*.md,
    │   glossary*.md, GLOSSARY*.md, domain*.md, ontology*.md,
    │   terms*.md, README.md
    ├─ Present candidates in a single message with select / add / "none"
    ├─ Write "### Domain docs" block to CLAUDE.md
    │   - Create CLAUDE.md if absent (with user confirmation)
    │   - Append "## Agent skills" if absent
    │   - "### Domain docs" subsection only if missing
    └─ Fall through to [3]

[3] Runtime (mattpocock grill-with-docs principles)
    ├─ Read all alias files; check for CONTEXT.md / CONTEXT-MAP.md
    ├─ Multi-context inference (if CONTEXT-MAP.md present):
    │   one question to confirm which context the work belongs to
    ├─ Grill loop (one question per message):
    │   - Flag terminology conflicts against the glossary
    │   - Sharpen fuzzy/overloaded terms
    │   - Cross-reference code where possible (read code instead of asking)
    │   - Update CONTEXT.md inline as terms resolve (lazy create)
    │   - Continue until user EXPLICITLY signals stop
    │     (skip / 넘어가자 / ok 진행 / proceed); model never auto-stops
    │
[4] Handoff → superpowers:brainstorming
```

### Document language policy

New/updated `CONTEXT.md` content follows the dominant language of the aliased domain docs. If aliases are mixed or empty, the skill asks once during the first grill round. Korean and English are both first-class.

### Brainstorming context propagation

After handoff, brainstorming inherits the conversation context naturally — the alias file contents and `CONTEXT.md` updates are already in the session. No explicit data pipe required.

## Format Files

### `CONTEXT-FORMAT.md`

Ports mattpocock's CONTEXT.md format verbatim:

- **Language**: term definitions (one sentence each), with `_Avoid_:` aliases to discourage.
- **Relationships**: cardinality between terms (`An Order produces one or more Invoices`).
- **Example dialogue**: dev ↔ domain expert exchange demonstrating term usage.
- **Flagged ambiguities**: previously overloaded terms and their resolution.

Rules: opinionated, one-sentence definitions, domain-only (no general programming concepts), bold term names, lazy creation, language follows aliased docs.

### `CONTEXT-MAP-FORMAT.md`

Ports mattpocock's multi-context map verbatim:

- Contexts list (path + one-line description)
- Cross-context relationships (event flows, shared types)
- Inference rules:
  - `CONTEXT-MAP.md` exists → multi-context
  - Only root `CONTEXT.md` → single context
  - Neither → lazy create root `CONTEXT.md` on first term resolution

### `BOOTSTRAP.md`

1. **Candidate scan** — case-insensitive filename match against the patterns at depth 1–2 from project root. Skip `node_modules/`, `.git/`, `dist/`, `build/`. Do not follow symlinks. Only include regular files ending in `.md`; if a pattern resolves to a directory or a non-`.md` file, skip silently.
2. **Presentation format** — one message containing the candidate list and the response menu (`select numbers` / `add path` / `none`).
3. **CLAUDE.md write template**:

   ```md
   ## Agent skills

   ### Domain docs
   <!-- managed by loading-domain-context skill -->
   - SCHEMA.md
   - FEATURES.md
   ```

   - Append `## Agent skills` to file end if missing.
   - Replace existing `### Domain docs` subsection if present (keeping the HTML comment marker).
4. **CLAUDE.md absent** — confirm once before creating; if user refuses, abort bootstrap and hand off.

## Edge Cases

| Situation | Handling |
|---|---|
| User invokes `/superpowers:brainstorming` directly | Bypass our skill (deliberate choice) |
| `CLAUDE.md` absent + user refuses creation | Abort bootstrap, hand off with no registry; retry next time |
| Aliased file no longer exists, resolves to a directory, or is not a `.md` file | Surface as "missing/invalid", one prompt: remove / fix path / leave; update `CLAUDE.md` accordingly |
| Multi-context but work scope unclear | One inference question; "all contexts" answer enables cross-context conflict detection |
| Existing `CONTEXT.md` is free-form (not mattpocock format) | Read as-is, never reformat. New entries lazy-add Language/Relationships sections only when first needed |
| User says `skip` immediately | Hand off with zero grill questions |
| `### Domain docs` block corrupted (HTML comment marker missing) | Re-run bootstrap after notifying user |

## Testing

Manual scenarios run after install:

1. **Empty new project** (no `CLAUDE.md`, no domain docs) — feature request triggers skill → bootstrap → "none" → empty registry → handoff.
2. **hwi_PKM (first real target)** — `SCHEMA.md`, `FEATURES.md` auto-detected → user confirms → block written → grill 1–2 questions → handoff.
3. **Repeat invocation** — block already present → bootstrap skipped → grill starts → `skip` ends loop → handoff.
4. **Alias file missing** — temporarily rename `SCHEMA.md` → skill flags missing → user picks "remove" → `CLAUDE.md` updated → grill continues.
5. **Trigger priority** — bug fix request ("fix X") → observable pass criterion: the very first assistant message after the user prompt must come from `loading-domain-context` (e.g., a bootstrap candidate list or a grill question), not from `superpowers:brainstorming` (which would start by asking about purpose/constraints).
6. **Free-form CONTEXT.md preservation** — pre-existing free-form `CONTEXT.md` retained; new term added under appended Language section without rewriting earlier content.

Trigger matching is model-driven; not unit-testable. File-mutation steps could ship a dry-run mode but YAGNI — manual verification suffices.

## Open Questions / Risks

- **Handoff reliability**: skill chaining depends on the model honoring the explicit `## Handoff` instruction. If a future Claude version regresses on this, fallback options:
  - Add a sentinel pattern to the handoff block that increases salience.
  - Add a hint in user-level `CLAUDE.md` reinforcing the order.
- **Description-trigger collisions** with future skills using similar wording. Monitor when adding more pre-skills.
- **Multi-context inference accuracy**: the one-question disambiguation may be insufficient for projects with overlapping contexts. Acceptable for v1; revisit if it surfaces in real use.
- **`CLAUDE.md` shape**: many projects use `CLAUDE.md` for free-form notes. Our `## Agent skills` section is additive; the HTML comment marker prevents most collisions. If a user already has a `## Agent skills` section with different sub-structure, we append `### Domain docs` under it.

## References

- `mattpocock/skills` — https://github.com/mattpocock/skills
  - `skills/engineering/grill-with-docs/SKILL.md`
  - `skills/engineering/grill-with-docs/CONTEXT-FORMAT.md`
- `superpowers:brainstorming` — `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.5/skills/brainstorming/SKILL.md`
- `superpowers:using-superpowers` — skill priority ordering rules
