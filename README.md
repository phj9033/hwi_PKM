# hwi_PKM

Personal Knowledge Management system. Markdown files are the source of truth; Claude Code orchestrates a deterministic `pkm` CLI to capture, curate, promote, and search knowledge.

See `docs/superpowers/specs/2026-05-01-pkm-design.md` for the full design.

## Quick start

```bash
uv sync --all-extras
pkm init                  # scaffold a fresh PKM (data/, .pkm/, SCHEMA.md, .claude/)
pkm doctor                # check environment + structure
```

## Commands

After `pkm init`:

- **Capture / chunks (M2):** `pkm capture {create,list,show,set-status,rm}`, `pkm chunks {new,add,list,show,set-status}`.
- **Indexing & search (M3):** `pkm reindex db [--full]`, `pkm search <query>`.
- **Git auto-commit (M3.5):** every mutation commits via `pkm <type>: <ref>`.
- **Extract (M4):** `pkm extract <file> [--out PATH]` — PDF/HTML → markdown. Install: `pip install -e '.[extract]'` (`pdfplumber` + `markdownify`).
- **Promote / demote (M4):** `pkm promote <ref> --to <bucket> [--slug NEW] [--keep-source]`, `pkm demote <wiki-ref>`.
- **Wiki edit (M4):** `pkm wiki edit <ref> {--replace|--patch}` — strict-mode escape valve.
- **Lint (M4):** `pkm lint [--fix] [--json] [--errors-only]` — 13 rules (6 errors, 7 warnings); `--fix` handles `MISSING_FIELD` + `ORPHAN_PROMOTED_SOURCE`.
- **Search enhancements (M5):**
  - `pkm search ... --no-rerank` skips the cross-encoder.
  - `pkm search ... --expand` enables LLM-mediated query expansion.
  - `pkm search ... --with-related` adds backlinks + semantic neighbors per hit.
- **Relations (M5):** `pkm related <path> [--mode backlinks|semantic|both] [-n N] [--json]`.
- **Writing (M5):** `pkm write {new,list,set-status}`. `pkm promote` and `pkm demote` accept `data/writing/*` sources.
- **AI bridge (M5):** `pkm/llm_bridge.py` autodetects `claude/codex/gemini/ollama` on PATH or follows TOML config in `.pkm/config.{toml,local.toml}`. `.pkm/hooks/<task>.sh` is an escape valve.
- **Models (M5):** `pkm doctor --download` fetches embedder + reranker (~1.2GB) into `~/.cache/pkm/models/`.
- **Slash templates seeded by init:** `/collect`, `/research`, `/review-captures`, `/promote`, `/lint`, `/ask`, `/write`.

## Status

- [x] M1 — Foundation (this milestone)
- [x] M2 — Capture & Chunks
- [x] M3 — Indexing & Search
- [x] M3.5 — Git Auto-commit
- [x] M4 — Promote, Lint & Extract
- [x] M5 — AI bridge & Writing
- [ ] M6 — Dashboard
- [ ] M7 — Hardening

(See spec §9.3 for milestone definitions.)
