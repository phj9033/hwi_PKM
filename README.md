# hwi_PKM

Personal Knowledge Management system. Markdown files are the source of truth; Claude Code orchestrates a deterministic `pkm` CLI to capture, curate, promote, and search knowledge.

See `docs/superpowers/specs/2026-05-01-pkm-design.md` for the full design.

## Quick start

```bash
uv sync --all-extras
pkm init                  # scaffold a fresh PKM (data/, .pkm/, SCHEMA.md, .claude/)
pkm doctor                # check environment + structure
```

## Status

- [x] M1 — Foundation (this milestone)
- [x] M2 — Capture & Chunks
- [ ] M3 — Indexing & Search
- [ ] M4 — Promote & Lint
- [ ] M5 — AI bridge & Writing
- [ ] M6 — Dashboard
- [ ] M7 — Hardening

(See spec §9.3 for milestone definitions.)
