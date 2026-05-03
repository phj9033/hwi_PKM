# hwi_PKM

Solo personal-knowledge-management. Markdown is the source of truth; a
deterministic `pkm` CLI handles capture, curation, indexing, promotion to
wiki, AI-assisted writing, and a static HTML dashboard. Designed to be
driven from Claude Code.

See `docs/superpowers/specs/2026-05-01-pkm-design.md` for the full V1 design.

## Quick start (3 minutes)

```bash
git clone <repo> hwi_pkm && cd hwi_pkm
uv sync --all-extras
pkm init                    # scaffold data/, .pkm/, SCHEMA.md, .claude/
pkm doctor                  # verify environment + structure
pkm doctor --download       # fetch bge-m3 + reranker (~1.2 GB, one time)
pkm capture create --slug hello --title "First note" --url https://x <<<"본문"
pkm capture set-status hello reviewed
pkm reindex db --full
pkm search "first"
pkm dashboard build && open dashboard/index.html
```

Or `pkm bootstrap` once after the first sync — it chains
`doctor --download → reindex db --full → dashboard build`.

## Commands (compact)

| Group | Commands |
|---|---|
| Setup | `pkm init`, `pkm doctor [--strict] [--download] [--json]`, `pkm bootstrap` |
| Capture / chunks | `pkm capture {create,list,show,set-status,rm}`, `pkm chunks {new,add,list,show,set-status}` |
| Index / search | `pkm reindex db [--full] [--low-memory]`, `pkm search <q> [--no-rerank] [--expand] [--with-related] [--json]`, `pkm related <path> [--mode backlinks|semantic|both]` |
| Promote / lint | `pkm promote <ref> --to <bucket>`, `pkm demote <ref>`, `pkm wiki edit <ref> {--replace|--patch}`, `pkm lint [--fix] [--json] [--errors-only]` |
| Extract | `pkm extract <file>` (PDF/HTML → md, requires `[extract]` extra) |
| Writing | `pkm write {new,list,set-status}` (writing → wiki promotion uses the same `pkm promote`) |
| Dashboard | `pkm dashboard build [--out PATH]` |
| Bench | `pkm bench [--docs N=100] [--real] [--json]` (M7) |
| Log | `pkm log` |

Slash commands seeded by `pkm init`: `/collect`, `/research`, `/review-captures`, `/promote`, `/lint`, `/ask`, `/write`.

## Where things live

```
data/                # markdown source of truth (raw/, wiki/, writing/)
.pkm/                # local index + config (gitignored except .pkm/config.toml)
.pkm/index.db        # SQLite + sqlite-vec
dashboard/           # static HTML (gitignored — rebuild with `pkm dashboard build`)
.claude/commands/    # slash command templates
SCHEMA.md            # the AI agent's source of truth for workflow rules
docs/superpowers/    # design spec + per-milestone plans
```

## Failure contract

Every error is a `PKMError` subclass with a stable `code` (e.g.
`NOT_FOUND`, `STATUS_NOT_REVIEWED`, `EXPAND_FAILED`). Failures exit
non-zero, print `Error [<CODE>]: <message>` to stderr, and emit
`{"ok": false, "error": {"code", "message", "hint"}}` to stdout in
`--json` mode. The full code list is the source-of-truth in
`pkm/errors.py`; coverage is verified by
`tests/test_failure_mode_matrix.py`.

## Status

- [x] M1 — Foundation
- [x] M2 — Capture & Chunks
- [x] M3 — Indexing & Search
- [x] M3.5 — Git Auto-commit
- [x] M4 — Promote, Lint & Extract
- [x] M5 — AI bridge & Writing
- [x] M6 — Dashboard
- [x] M7 — Hardening (V1 GA)

V1 ship checklist: `docs/M7-SHIP-CHECKLIST.md`.
