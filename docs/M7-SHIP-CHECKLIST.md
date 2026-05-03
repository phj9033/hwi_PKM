# M7 SHIP CHECKLIST

> Verify before tagging `m7-hardening`. One section per §9.4 V1 acceptance bullet.

## 1. 6 user features through slash + CLI

- [ ] `/collect` — capture from URL.
- [ ] `/research` — gather + summarize.
- [ ] `/review-captures` — bulk status sweep.
- [ ] `/promote` — capture → wiki.
- [ ] `/lint` — fix + report.
- [ ] `/ask` — pkm search → Read → synthesize (Claude Code session, no AI CLI).
- [ ] `/write` — write new + promote.

## 2. New PC fresh-clone end-to-end

```bash
git clone <repo> /tmp/pkm-fresh && cd /tmp/pkm-fresh
uv sync --all-extras
pkm bootstrap
ls dashboard/index.html
```

Expected: bootstrap exits 0, dashboard/index.html exists, `pkm doctor` is all ✓.

## 3. 100-doc Korean perf budget

```bash
pkm bench --real --docs 100
```

Expected: `reindex < 300s` (5 min) and `search p95 < 2000 ms` printed.
**This is a soft threshold** — the bench prints values; you eyeball the budget.

## 4. `pkm doctor` all green

```bash
pkm doctor --strict
```

Expected: every row ✓, exit 0.

## 5. Test budgets

```bash
time uv run pytest -n auto -m "not slow"     # < 120s locally
time uv run pytest -m slow -n 0              # < 600s
```

Plus: peak RSS during fast suite stays < 4 GB (enforced by `tests/test_perf_gate.py` + `_rss_guard`).

## 6. Failure-mode coverage 100%

```bash
uv run pytest tests/test_failure_mode_matrix.py tests/test_error_registry.py -v
```

Expected: every PKMError code is exercised; deferred codes (PKM_ERROR base, NOT_IMPLEMENTED parent, PROMOTE_FROM_WRITING_NOT_YET, DEMOTE_TO_WRITING_NOT_YET) skip with a documented reason.

## 7. Docs

- [ ] `README.md` — V1 quick start, command index, failure contract present.
- [ ] `pkm/templates/SCHEMA.md.template` — bench row + failure section present.
- [ ] `pkm dashboard build && open dashboard/help.html` — bench row + failure-code table present.

## 8. Strict mode rejects direct wiki write

In strict mode, attempting `Write` against `data/wiki/**` from Claude Code must be denied. Manually verify by toggling mode and editing.

## 9. All mutate auto-commits + `--no-git` deny

```bash
pkm capture set-status X reviewed --no-git
```

Expected: `Error [...]: --no-git is not permitted in strict mode`.

## 10. Claude Code `/ask` flow without external AI CLI

In a fresh Claude Code session inside the repo:

1. Run `/ask "What is X?"`.
2. Confirm Claude calls `pkm search`, reads top-K files, then synthesizes a citation-grounded answer **without invoking any external `claude`/`codex`/`gemini` CLI**.

## 11. Optional: AI CLI `--expand` opt-in

After installing & authenticating an AI CLI:

```bash
pkm search "임베딩" --expand
```

Expected: query expands, hits returned, exit 0.

---

When every box is ticked: tag `m7-hardening` (`git tag -a m7-hardening -m "V1 GA"`).
