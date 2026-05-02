# M4 — Promote, Lint & Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the spec §6 promote / lint pipeline + the §3.2 `pkm extract` command. After M4 a capture can be promoted to a wiki bucket, a wiki page can be patched in-place via the strict-mode escape valve, broken/stale state is detected by `pkm lint`, and binary documents (PDF/local HTML) can be turned into markdown captures.

**Architecture:** Three new command groups — `extract`, `promote` / `demote`, `wiki edit`, `lint` — each pinned to a thin module under `pkm/commands/` and a small library under `pkm/extract/` or `pkm/lint/`. The wiki + writing frontmatter schemas land first so promote and lint can validate against the same shape. The 4-step `post_mutation` chain (M2 log → TOC → M3 reindex → M3.5 git commit) gains no new step in M4 — every promote/demote/wiki edit just calls `post_mutation` with both source and destination paths so reindex and git see the move correctly. `pkm lint` is read-only by default; `--fix` mutates frontmatter and goes through `post_mutation` like every other write.

**Tech Stack:** New runtime deps `pdfplumber>=0.11`, `markdownify>=0.13` under a new `extract` extras group (`pip install hwi-pkm[extract]`). Stdlib `subprocess` for `git apply` (already a dep via M3.5). No new test infra.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md`
- §3.2 (commands — extract, promote, demote, wiki edit, lint)
- §4.3 (strict mode + wiki edit escape valve)
- §6.1 (frontmatter schemas — wiki + writing)
- §6.2 (status transitions)
- §6.3 (promote gate)
- §6.4 (demote)
- §6.5 (lint rules — Errors + Warnings + V2 deferral)
- §6.6 (auto side-effects — already covered by M2/M3/M3.5)

The master spec text remains canonical; M4 implements §3.2 extract + §6 (sans `--deep` + sans `pkm write *`).

---

## Scope decisions (locked from brainstorming, 2026-05-02)

| # | Decision | Outcome |
|---|---|---|
| 1 | `pkm extract` source formats | **PDF + local HTML.** docx is V2-deferred. Deps: `pdfplumber` + `markdownify` under a new `[extract]` extras group. URL fetch stays with `pkm capture create --url`; extract is for local binaries. |
| 2 | `pkm wiki edit` input modes | **`--replace` AND `--patch` both shipped.** `--replace` reads stdin as the entire file (frontmatter+body). `--patch` reads stdin as a unified diff and applies via `git apply` shell-out. Both go through the same validation gate (frontmatter + wikilink integrity) before commit. |
| 3 | Wiki + writing frontmatter schemas | **Both ship in M4.** `pkm/store/frontmatter_schemas.py` grows `wiki_defaults / validate_wiki` and `writing_defaults / validate_writing`. The `pkm write new` command itself is M5 — M4 just lays the schema down so promote and lint can validate writing files when the user authors them by hand or copies them from another tool. |
| 4 | M4 vs M5 boundary for promote/demote | **`pkm promote` and `pkm demote` only handle the capture↔wiki round-trip in M4.** When the input path is under `data/writing/`, both commands return a clear `PROMOTE_FROM_WRITING_NOT_YET` error (code stable, M5 will add the writing branch). `pkm write new` itself stays M5. |
| 5 | `pkm lint --fix` scope | **Detect 13 rules (6 Errors + 7 Warnings); auto-fix only the 2 the spec explicitly marks.** Auto-fix: `MISSING_FIELD` (only `created_at: <mtime>` and `slug: <kebab(title)>`) + `ORPHAN_PROMOTED_SOURCE` (set source `status: archived`). Everything else is detect-only in M4. `--deep` (LLM lint) stays V2. |
| 6 | `pkm init` slash command seeding | **Add `/promote` and `/lint` templates** (total seeded: 5 commands — `collect`, `research`, `review-captures`, `promote`, `lint`). The remaining 3 spec-listed slash commands (`ask`, `write`, `chunk-synthesis`) stay deferred to M5/M6 because they need AI bridge or write-side commands that don't exist yet. |
| 7 | `pkm doctor` extension | **No change.** Schema + lint state are reported by `pkm lint --json`, not by doctor. Doctor stays focused on environment health (Python, paths, index.db, model cache, git CLI). |

After M4, the user can:

```bash
# Extract
pkm extract paper.pdf --out data/raw/captures/2026-05-02-paper.md
# Wiki round-trip via promote
pkm capture set-status 2026-05-02-foo reviewed
pkm promote 2026-05-02-foo --to concepts            # creates data/wiki/concepts/foo.md, archives source
pkm demote data/wiki/concepts/foo.md                 # restores capture status=reviewed
# Strict-mode escape valve
echo "..." | pkm wiki edit data/wiki/concepts/foo.md --replace
git diff data/wiki/concepts/foo.md | pkm wiki edit data/wiki/concepts/foo.md --patch
# Lint
pkm lint --json
pkm lint --fix --errors-only
# Slash templates seeded by init
ls .claude/commands/   # collect, research, review-captures, promote, lint
```

---

## File Structure

### Created in M4

```
pkm/extract/__init__.py
pkm/extract/pdf.py                 # pdfplumber → markdown
pkm/extract/html.py                # markdownify → markdown

pkm/lint/__init__.py
pkm/lint/rules.py                  # detection: 6 Errors + 7 Warnings as a uniform LintFinding stream
pkm/lint/fixers.py                 # auto-fix logic (only the 2 spec-marked items)

pkm/commands/extract.py            # CLI: pkm extract <file> [--out PATH]
pkm/commands/promote.py            # CLI: pkm promote <ref> --to BUCKET [...]
pkm/commands/demote.py             # CLI: pkm demote <wiki-path>
pkm/commands/wiki.py               # CLI subgroup: pkm wiki edit
pkm/commands/lint.py               # CLI: pkm lint [--fix] [--json] [--errors-only]

pkm/store/wiki_paths.py            # bucket/slug ↔ path helpers, resolve_wiki()

pkm/templates/.claude/commands/promote.md
pkm/templates/.claude/commands/lint.md

tests/test_extract_pdf.py
tests/test_extract_html.py
tests/test_extract_command.py
tests/test_frontmatter_schemas_wiki.py
tests/test_frontmatter_schemas_writing.py
tests/test_wiki_paths.py
tests/test_wiki_edit_replace.py
tests/test_wiki_edit_patch.py
tests/test_promote.py
tests/test_demote.py
tests/test_lint_errors.py
tests/test_lint_warnings.py
tests/test_lint_command.py
tests/test_init_m4_seeds.py        # init seeds /promote + /lint
tests/fixtures/extract/             # tiny PDF + HTML samples (committed binaries OK)
```

### Modified in M4

```
pkm/store/frontmatter_schemas.py    # + wiki_defaults / validate_wiki
                                    # + writing_defaults / validate_writing
pkm/store/refs.py                   # (small) resolve_wiki helper used by demote/wiki edit
pkm/commands/init.py                # seeds 2 more slash templates + bumps SCHEMA.md note
pkm/templates/SCHEMA.md.template    # § 3 wiki/writing schema entries; § 6 add Promote / Wiki Edit / Lint workflows
pkm/cli.py                          # register new commands
pyproject.toml                      # + [extract] extras group
README.md                           # mark M4 done
```

### Why these boundaries

- **`pkm/extract/`** isolates the heavy parser deps (`pdfplumber` + `markdownify`) behind a lazy import. The CLI module imports these inside the function body so `pkm --help` stays fast and unit tests for command wiring don't need the deps.
- **`pkm/lint/rules.py` is a single file with 13 rule functions** that all return `LintFinding` records. One module = one place to look for "what does lint check?" and the rule signatures stay uniform. Splitting per-rule is overengineering for V1.
- **`pkm/lint/fixers.py`** is the only place that knows how to mutate frontmatter to fix a finding. It's separate from `rules.py` so a future deep-lint or `--dry-run` can reuse the rule layer without inheriting the fixer machinery.
- **`pkm/store/wiki_paths.py`** holds the `bucket → directory` mapping and the `resolve_wiki(root, ref_or_path, bucket=None) → Path` helper. promote/demote/wiki edit all share these. We don't fold this into `refs.py` because `refs.py` stays scoped to capture/chunk lookups (M2 invariant — wiki was deny-write before M4).
- **`commands/wiki.py`** owns the `pkm wiki ...` subgroup. M4 ships only `edit`; future `wiki list`, `wiki show`, etc. land here.
- **`commands/promote.py` and `commands/demote.py` are separate files** even though they share helpers, because their CLI surface and their gate logic are genuinely different and merging them would force one of the two test files to bear the other's setup cost.

---

## Out of scope (deferred)

| Item | Where it goes | Why |
|---|---|---|
| docx → markdown | V2 | `python-docx` table/image fidelity is poor; user workflow doesn't lean on docx |
| `pkm promote data/writing/<s>.md` | M5 | Needs `pkm write new` to populate writing files first |
| `pkm demote` of writing-derived wiki | M5 | Pairs with the M5 promote-from-writing branch |
| `pkm write new` | M5 | Spec §9.3 puts write in Week 5-6 with AI bridge |
| `pkm lint --deep` (LLM-mediated rules: `CONTRADICTION` / `DATA_GAP` / `STALE_CLAIM`) | V2 | Spec §6.5 explicit |
| Auto-fix beyond the 2 spec-marked items | V2 | Avoid scope creep; spec doesn't define safe auto-fixes for the rest |
| `pkm wiki list` / `wiki show` / `wiki rm` | V2 (read-only access via filesystem + `pkm search` covers V1) | |
| `pkm doctor` schema item | not planned | `pkm lint --errors-only` is the canonical schema check |
| `EMBED_MODEL_MISSING` / `INDEX_SCHEMA_MISMATCH` failure-mode codes (spec §5.7) | M7 hardening | Carved over from M3 |

---

## Conventions for the executor

> Active venv: `.venv/`. `.venv/bin/pytest` and `.venv/bin/pkm` work. Forward-only commits on `main`. Each task ends with one commit prefixed `M4.<n>:`. Plan-deviation fixes use `fix:` prefix per project convention.
>
> `PKM_TEST_STUB_EMBEDDER=1` is set globally by `tests/conftest.py` — no test should need to set it again. Heavy deps (`pdfplumber`, `markdownify`) are imported inside function bodies, never at module top-level, so `pytest --collect-only` stays fast.
>
> `validate_capture` and friends raise `PKMValidationError`. Promote/demote/wiki edit/lint should let those bubble up to the CLI layer, which already has the JSON error shape from M2.
>
> Every mutate command (extract, promote, demote, wiki edit, lint --fix) MUST call `post_mutation(root, LogEvent(...), paths=[...])` and include the returned `git_commit: <sha>` in its JSON output. Source AND destination paths go in `paths` (renames need both).

---

## Task list

14 tasks. Tasks 1–13 are TDD; Task 14 is acceptance.

| # | Task | TDD? | Approx tests |
|---|---|---|---|
| 1 | `pkm/extract/pdf.py` + `html.py` library modules | yes | 6–8 |
| 2 | `pkm extract` CLI command | yes | 4 |
| 3 | wiki + writing frontmatter schemas | yes | 8–10 |
| 4 | `pkm/store/wiki_paths.py` helpers | yes | 5 |
| 5 | `pkm wiki edit --replace` | yes | 5 |
| 6 | `pkm wiki edit --patch` (git apply) | yes | 4 |
| 7 | `pkm promote` (capture → wiki) | yes | 9 |
| 8 | `pkm demote` (wiki → capture) | yes | 5 |
| 9 | `pkm capture set-status reviewed` records `body_hash` | yes | 4 |
| 10 | `pkm/lint/rules.py` — 6 Errors + 7 Warnings | yes | 13 (one per rule) |
| 11 | `pkm/lint/fixers.py` — 2 auto-fixes | yes | 5 |
| 12 | `pkm lint` CLI + `--fix` + `--json` + `--errors-only` | yes | 5 |
| 13 | Slash templates (`/promote` + `/lint`) seeded by `pkm init` | yes | 2 |
| 14 | README + SCHEMA.md updates + lint clean + tag | no | — |

**Estimated test delta:** ~74 new tests on top of the 180 baseline → ~254 fast tests after M4.

---

### Task 1: `pkm/extract/` library modules (TDD)

**Files:**
- Create: `pkm/extract/__init__.py`, `pkm/extract/pdf.py`, `pkm/extract/html.py`
- Test: `tests/test_extract_pdf.py`, `tests/test_extract_html.py`
- Fixtures: `tests/fixtures/extract/sample.pdf`, `tests/fixtures/extract/sample.html`
- Modify: `pyproject.toml` (add `[extract]` extras)

**Goal:** Two pure functions — `pdf_to_markdown(path) → str` and `html_to_markdown(path) → str` — with no CLI surface. Heavy deps imported inside functions so the test collection stays fast.

#### Steps

- [ ] **Step 1.1: Add `[extract]` extras to `pyproject.toml`**

In `pyproject.toml` under `[project.optional-dependencies]`, add a new group between `ml` and `dev`:

```toml
extract = [
    "pdfplumber>=0.11",
    "markdownify>=0.13",
]
```

Run `uv pip install -e '.[extract]'` (or pip equivalent) and verify both deps install.

- [ ] **Step 1.2: Add binary fixtures**

Create `tests/fixtures/extract/` and put two tiny test files:
- `sample.pdf` — a 1-page PDF with the text `Hello, PDF world.` and `한국어 본문` on a second line. Generate it locally with reportlab in a one-off script, OR use any small handcrafted PDF you have. Commit it.
- `sample.html` — paste the following content:

```html
<!DOCTYPE html>
<html lang="ko">
<head><title>Sample Page</title></head>
<body>
<h1>샘플 제목</h1>
<p>This is the <strong>first</strong> paragraph.</p>
<ul><li>한 항목</li><li>another item</li></ul>
</body>
</html>
```

Both files are <10 KB. They live at `tests/fixtures/extract/`.

- [ ] **Step 1.3: Write failing tests `tests/test_extract_pdf.py`**

```python
"""Tests for pkm.extract.pdf."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.extract import pdf as pdfmod

FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_pdf_to_markdown_extracts_text():
    out = pdfmod.pdf_to_markdown(FIXTURES / "sample.pdf")
    assert "Hello, PDF world." in out
    assert "한국어" in out


def test_pdf_to_markdown_returns_unicode():
    out = pdfmod.pdf_to_markdown(FIXTURES / "sample.pdf")
    assert isinstance(out, str)
    # No mojibake — the original characters survive
    assert "한국어 본문" in out


def test_pdf_to_markdown_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        pdfmod.pdf_to_markdown(tmp_path / "does-not-exist.pdf")
```

- [ ] **Step 1.4: Write failing tests `tests/test_extract_html.py`**

```python
"""Tests for pkm.extract.html."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.extract import html as htmlmod

FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_html_to_markdown_h1():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    # markdownify emits "# 샘플 제목" or "샘플 제목\n=====" — accept either form
    assert "샘플 제목" in out
    assert ("# " in out) or ("=" * 3 in out)


def test_html_to_markdown_strong_to_asterisks():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    assert "**first**" in out


def test_html_to_markdown_list_items():
    out = htmlmod.html_to_markdown(FIXTURES / "sample.html")
    assert "한 항목" in out
    assert "another item" in out


def test_html_to_markdown_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        htmlmod.html_to_markdown(tmp_path / "missing.html")
```

- [ ] **Step 1.5: Run the failing tests**

```bash
.venv/bin/pytest tests/test_extract_pdf.py tests/test_extract_html.py -v
```

Expected: all 7 tests fail with `ModuleNotFoundError: No module named 'pkm.extract'`.

- [ ] **Step 1.6: Implement `pkm/extract/__init__.py`**

```python
"""Document → markdown extractors.

Two formats in M4:
- PDF via `pdfplumber` (text only; tables → simple text)
- local HTML via `markdownify`

URLs go through `pkm capture create --url` (M2) — extract is for local
binaries already on disk.

Heavy deps (pdfplumber, markdownify) are imported lazily inside each
function so that `pkm --help` and bare test collection don't pay the cost.
"""
```

- [ ] **Step 1.7: Implement `pkm/extract/pdf.py`**

```python
"""PDF → markdown via pdfplumber."""
from __future__ import annotations

from pathlib import Path


def pdf_to_markdown(path: Path) -> str:
    """Extract text from a PDF file and return as markdown.

    Strategy: pdfplumber's `page.extract_text()` per page, joined with
    blank lines. No table rendering yet — V2 may add `extract_tables()`
    → markdown table conversion.
    """
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    import pdfplumber  # lazy

    pages_text: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text.strip())
    return "\n\n".join(p for p in pages_text if p)
```

- [ ] **Step 1.8: Implement `pkm/extract/html.py`**

```python
"""Local HTML → markdown via markdownify."""
from __future__ import annotations

from pathlib import Path


def html_to_markdown(path: Path) -> str:
    """Convert a local HTML file to markdown.

    Strategy: read the file, hand it to `markdownify.markdownify()`. The
    result is GFM-flavored (lists, headers, emphasis, links). The caller
    decides whether to add a frontmatter block or wrap as a capture.
    """
    if not path.exists():
        raise FileNotFoundError(f"HTML not found: {path}")
    import markdownify  # lazy

    raw = path.read_text(encoding="utf-8")
    return markdownify.markdownify(raw, heading_style="ATX").strip()
```

- [ ] **Step 1.9: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_extract_pdf.py tests/test_extract_html.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 1.10: Commit**

```bash
git add pyproject.toml pkm/extract/ tests/test_extract_pdf.py tests/test_extract_html.py tests/fixtures/extract/
git commit -m "$(cat <<'EOF'
M4.1: pkm.extract — PDF + HTML → markdown library modules

Adds [extract] extras (pdfplumber + markdownify). Two pure functions
with lazy imports so test collection stays fast. CLI surface lands in M4.2.
EOF
)"
```

---

### Task 2: `pkm extract` CLI command (TDD)

**Files:**
- Create: `pkm/commands/extract.py`, `tests/test_extract_command.py`
- Modify: `pkm/cli.py` (register the command)

**Goal:** A single command `pkm extract <file> [--out PATH] [--json]`. By default it writes the markdown to stdout. With `--out`, it atomically writes to a path. Format dispatch is by file extension: `.pdf` → pdf module, `.html` / `.htm` → html module.

This is NOT a mutate command — it doesn't go through `post_mutation`. It just produces text. The user pipes the output into `pkm capture create` if they want a capture (or uses `--out` to write somewhere arbitrary — common workflow is `--out data/raw/captures/<slug>.md` followed by hand-editing).

#### Steps

- [ ] **Step 2.1: Write failing tests `tests/test_extract_command.py`**

```python
"""Tests for `pkm extract` CLI."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "extract"


def test_extract_pdf_to_stdout():
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.pdf")])
    assert result.exit_code == 0
    assert "Hello, PDF world." in result.stdout


def test_extract_html_to_stdout():
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.html")])
    assert result.exit_code == 0
    assert "샘플 제목" in result.stdout
    assert "**first**" in result.stdout


def test_extract_to_out_path(tmp_path: Path):
    out = tmp_path / "extracted.md"
    result = runner.invoke(app, ["extract", str(FIXTURES / "sample.pdf"), "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Hello, PDF world." in content


def test_extract_unknown_extension_errors(tmp_path: Path):
    weird = tmp_path / "doc.docx"
    weird.write_bytes(b"not actually docx")
    result = runner.invoke(app, ["extract", str(weird), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_extract_command.py -v
```

Expected: 4 fails (no `extract` command registered).

- [ ] **Step 2.3: Implement `pkm/commands/extract.py`**

```python
"""`pkm extract <file>` — turn a local PDF or HTML into markdown.

Pure function command — does NOT go through post_mutation. The user
pipes the output into `pkm capture create` (or writes to `--out`). For
URL fetches use `pkm capture create --url ...` instead.

Spec reference: §3.2 (extract), §6 (V2 docx deferral).
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.errors import PKMError, PKMValidationError
from pkm.store.files import atomic_write


def _extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pkm.extract.pdf import pdf_to_markdown
        return pdf_to_markdown(path)
    if suffix in (".html", ".htm"):
        from pkm.extract.html import html_to_markdown
        return html_to_markdown(path)
    raise PKMValidationError(
        f"unsupported extension {suffix!r}",
        hint="Supported: .pdf, .html, .htm. docx is V2.",
    )


def register(app: typer.Typer) -> None:
    @app.command("extract")
    def extract_cmd(
        path: Path = typer.Argument(..., exists=True, readable=True,
                                    help="Source file (.pdf, .html, .htm)."),
        out: Path | None = typer.Option(None, "--out", help="Write markdown to this path (default: stdout)."),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON summary instead of raw markdown."),
    ) -> None:
        """Convert a local PDF or HTML file to markdown."""
        try:
            md = _extract(path)
        except FileNotFoundError as e:
            err = {"code": "NOT_FOUND", "message": str(e), "hint": None}
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": err}, ensure_ascii=False))
            else:
                typer.echo(f"Error [NOT_FOUND]: {e}", err=True)
            raise typer.Exit(code=1) from None
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None

        if out is not None:
            atomic_write(out, md)
            if json_out:
                typer.echo(json.dumps(
                    {"ok": True, "out": out.relative_to(Path.cwd()).as_posix() if out.is_absolute() else str(out),
                     "chars": len(md)}, ensure_ascii=False))
            else:
                typer.echo(f"Wrote {len(md)} chars → {out}")
        else:
            if json_out:
                typer.echo(json.dumps({"ok": True, "chars": len(md), "markdown": md}, ensure_ascii=False))
            else:
                typer.echo(md)
```

- [ ] **Step 2.4: Register in `pkm/cli.py`**

Add the import + register call alongside the existing M2/M3 commands (e.g. right after `search`):

```python
from pkm.commands import extract as extract_cmd  # noqa: F401
# ...
extract_cmd.register(app)
```

If unsure where the existing imports/registrations live, run:

```bash
grep -n "register" pkm/cli.py
```

and add yours in the same style. Keep imports alphabetized within the existing convention.

- [ ] **Step 2.5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_extract_command.py -v
```

Expected: 4 passes.

- [ ] **Step 2.6: Commit**

```bash
git add pkm/commands/extract.py pkm/cli.py tests/test_extract_command.py
git commit -m "$(cat <<'EOF'
M4.2: pkm extract <file> — PDF/HTML → markdown CLI

Dispatch by extension. --out writes atomically, default is stdout.
Pure transform — no post_mutation. docx is V2-deferred.
EOF
)"
```

---

### Task 3: wiki + writing frontmatter schemas (TDD)

**Files:**
- Modify: `pkm/store/frontmatter_schemas.py`
- Create: `tests/test_frontmatter_schemas_wiki.py`, `tests/test_frontmatter_schemas_writing.py`

**Goal:** Add `wiki_defaults / validate_wiki` and `writing_defaults / validate_writing` mirroring the M2 capture/chunk shape. Validation is shape-only; referential checks (paths exist, related slugs exist) live in `pkm lint`.

#### Steps

- [ ] **Step 3.1: Write failing tests `tests/test_frontmatter_schemas_wiki.py`**

```python
"""Tests for wiki frontmatter schema."""
from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import validate_wiki, wiki_defaults


def test_wiki_defaults_includes_required_fields():
    fm = wiki_defaults(slug="oauth-token-storage", title="OAuth Token Storage", bucket="concepts")
    for k in ("title", "slug", "bucket", "created_at", "updated_at", "status", "lang", "tags"):
        assert k in fm
    assert fm["status"] == "stub"
    assert fm["bucket"] == "concepts"
    assert fm["tags"] == []


def test_wiki_defaults_optional_promoted_from():
    fm = wiki_defaults(slug="x", title="X", bucket="notes",
                       promoted_from="data/raw/captures/2026-05-01-x.md")
    assert fm["promoted_from"] == "data/raw/captures/2026-05-01-x.md"


def test_validate_wiki_passes_minimal():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="entities")
    validate_wiki(fm)  # no raise


def test_validate_wiki_rejects_unknown_bucket():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="entities")
    fm["bucket"] = "garbage"
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)


def test_validate_wiki_rejects_unknown_status():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="concepts")
    fm["status"] = "weird"
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)


def test_validate_wiki_missing_required_field_raises():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="concepts")
    del fm["title"]
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)
```

- [ ] **Step 3.2: Write failing tests `tests/test_frontmatter_schemas_writing.py`**

```python
"""Tests for writing frontmatter schema."""
from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import validate_writing, writing_defaults


def test_writing_defaults_includes_required_fields():
    fm = writing_defaults(slug="team-oauth", title="Team OAuth Guideline",
                          purpose="guideline",
                          derived_from=["data/wiki/concepts/oauth.md"])
    for k in ("title", "slug", "created_at", "updated_at", "status", "purpose", "derived_from", "lang", "tags"):
        assert k in fm
    assert fm["status"] == "draft"
    assert fm["purpose"] == "guideline"
    assert fm["derived_from"] == ["data/wiki/concepts/oauth.md"]


def test_validate_writing_passes_minimal():
    fm = writing_defaults(slug="foo", title="F", purpose="report",
                          derived_from=["data/wiki/notes/x.md"])
    validate_writing(fm)  # no raise


def test_validate_writing_rejects_empty_derived_from():
    fm = writing_defaults(slug="foo", title="F", purpose="essay",
                          derived_from=[])
    with pytest.raises(PKMValidationError):
        validate_writing(fm)


def test_validate_writing_rejects_unknown_purpose():
    fm = writing_defaults(slug="foo", title="F", purpose="guideline",
                          derived_from=["data/wiki/concepts/x.md"])
    fm["purpose"] = "novel"
    with pytest.raises(PKMValidationError):
        validate_writing(fm)
```

- [ ] **Step 3.3: Run failing tests**

```bash
.venv/bin/pytest tests/test_frontmatter_schemas_wiki.py tests/test_frontmatter_schemas_writing.py -v
```

Expected: all fail with `ImportError` (the names don't exist yet).

- [ ] **Step 3.4: Extend `pkm/store/frontmatter_schemas.py`**

Append to the existing file (after `validate_chunk`):

```python
# --- wiki ---

_WIKI_REQUIRED = ("title", "slug", "bucket", "created_at", "updated_at", "status", "lang", "tags")
_WIKI_BUCKETS = ("concepts", "entities", "notes", "reports")
_WIKI_STATUSES = ("stub", "active", "deprecated")
_WIKI_LANGS = ("ko", "en", "mixed")


def wiki_defaults(
    *,
    slug: str,
    title: str,
    bucket: str,
    status: str = "stub",
    lang: str = "ko",
    tags: list[str] | None = None,
    promoted_from: str | None = None,
    derived_from: list[str] | None = None,
    related: list[str] | None = None,
) -> dict:
    """Build a frontmatter dict for a new wiki page."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "bucket": bucket,
        "created_at": now,
        "updated_at": now,
        "status": status,
        "lang": lang,
        "tags": list(tags) if tags else [],
    }
    if promoted_from:
        fm["promoted_from"] = promoted_from
    if derived_from:
        fm["derived_from"] = list(derived_from)
    if related:
        fm["related"] = list(related)
    return fm


def validate_wiki(fm: dict) -> None:
    _check_required(fm, _WIKI_REQUIRED, "wiki")
    _check_enum(fm, "bucket", _WIKI_BUCKETS, "wiki")
    _check_enum(fm, "status", _WIKI_STATUSES, "wiki")
    _check_enum(fm, "lang", _WIKI_LANGS, "wiki")
    if not isinstance(fm.get("tags"), list):
        raise PKMValidationError("wiki frontmatter `tags` must be a list")


# --- writing ---

_WRITING_REQUIRED = ("title", "slug", "created_at", "updated_at", "status", "purpose", "derived_from", "lang", "tags")
_WRITING_PURPOSES = ("guideline", "report", "summary", "essay")
_WRITING_STATUSES = ("draft", "final", "promoted", "abandoned")
_WRITING_LANGS = ("ko", "en", "mixed")


def writing_defaults(
    *,
    slug: str,
    title: str,
    purpose: str,
    derived_from: list[str],
    status: str = "draft",
    lang: str = "ko",
    tags: list[str] | None = None,
    search_seed: str | None = None,
) -> dict:
    """Build a frontmatter dict for a new writing artifact."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "created_at": now,
        "updated_at": now,
        "status": status,
        "purpose": purpose,
        "derived_from": list(derived_from),
        "lang": lang,
        "tags": list(tags) if tags else [],
    }
    if search_seed:
        fm["search_seed"] = search_seed
    return fm


def validate_writing(fm: dict) -> None:
    _check_required(fm, _WRITING_REQUIRED, "writing")
    _check_enum(fm, "purpose", _WRITING_PURPOSES, "writing")
    _check_enum(fm, "status", _WRITING_STATUSES, "writing")
    _check_enum(fm, "lang", _WRITING_LANGS, "writing")
    derived = fm.get("derived_from")
    if not isinstance(derived, list) or not derived:
        raise PKMValidationError(
            "writing frontmatter `derived_from` must be a non-empty list",
            hint="A writing artifact must trace back to at least one source.",
        )


# Public aliases — `pkm.lint.rules` consumes these to avoid importing
# underscore-prefixed names. The underscore versions remain the internal
# module-level reference for the validators above.
CAPTURE_REQUIRED = _CAPTURE_REQUIRED
CAPTURE_STATUSES = _CAPTURE_STATUSES
CAPTURE_SOURCE_TYPES = _CAPTURE_SOURCE_TYPES
CAPTURE_LANGS = _CAPTURE_LANGS
CHUNK_REQUIRED = _CHUNK_REQUIRED
CHUNK_STATUSES = _CHUNK_STATUSES
CHUNK_LANGS = _CHUNK_LANGS
WIKI_REQUIRED = _WIKI_REQUIRED
WIKI_BUCKETS = _WIKI_BUCKETS
WIKI_STATUSES = _WIKI_STATUSES
WIKI_LANGS = _WIKI_LANGS
WRITING_REQUIRED = _WRITING_REQUIRED
WRITING_PURPOSES = _WRITING_PURPOSES
WRITING_STATUSES = _WRITING_STATUSES
WRITING_LANGS = _WRITING_LANGS
```

- [ ] **Step 3.5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_frontmatter_schemas_wiki.py tests/test_frontmatter_schemas_writing.py -v
```

Expected: all 10 pass.

- [ ] **Step 3.6: Commit**

```bash
git add pkm/store/frontmatter_schemas.py tests/test_frontmatter_schemas_wiki.py tests/test_frontmatter_schemas_writing.py
git commit -m "$(cat <<'EOF'
M4.3: wiki + writing frontmatter schemas

wiki_defaults / validate_wiki — buckets concepts|entities|notes|reports,
statuses stub|active|deprecated. writing_defaults / validate_writing —
purposes guideline|report|summary|essay, statuses draft|final|promoted|abandoned,
non-empty derived_from required. Shape-only validation; referential
checks land in `pkm lint`.
EOF
)"
```

---

### Task 4: `pkm/store/wiki_paths.py` helpers (TDD)

**Files:**
- Create: `pkm/store/wiki_paths.py`, `tests/test_wiki_paths.py`

**Goal:** A tiny module shared by promote / demote / wiki edit / lint:

- `WIKI_BUCKETS: tuple[str, ...]` — single source of truth, mirrors the schema's `_WIKI_BUCKETS`
- `wiki_dir(root, bucket) → Path`
- `wiki_path(root, bucket, slug) → Path` — `data/wiki/<bucket>/<slug>.md`
- `resolve_wiki(root, ref) → Path` — accepts either `data/wiki/concepts/foo.md` (path) or `concepts/foo` (bucket/slug shorthand) or `foo` (slug, must be unambiguous across buckets)
- `iter_all_wiki(root) → Iterable[Path]` — every `*.md` under `data/wiki/<bucket>/`

#### Steps

- [ ] **Step 4.1: Write failing tests `tests/test_wiki_paths.py`**

```python
"""Tests for pkm.store.wiki_paths."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store import wiki_paths as wp


def _make_wiki(tmp_path: Path, bucket: str, slug: str) -> Path:
    p = tmp_path / "data" / "wiki" / bucket / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: t\n---\nbody\n", encoding="utf-8")
    return p


def test_wiki_dir(tmp_path: Path):
    assert wp.wiki_dir(tmp_path, "concepts") == tmp_path / "data" / "wiki" / "concepts"


def test_wiki_path(tmp_path: Path):
    assert wp.wiki_path(tmp_path, "notes", "foo") == tmp_path / "data" / "wiki" / "notes" / "foo.md"


def test_resolve_wiki_by_full_path(tmp_path: Path):
    p = _make_wiki(tmp_path, "concepts", "oauth")
    assert wp.resolve_wiki(tmp_path, "data/wiki/concepts/oauth.md") == p


def test_resolve_wiki_by_bucket_slash_slug(tmp_path: Path):
    p = _make_wiki(tmp_path, "entities", "anthropic")
    assert wp.resolve_wiki(tmp_path, "entities/anthropic") == p


def test_resolve_wiki_by_slug_unambiguous(tmp_path: Path):
    p = _make_wiki(tmp_path, "notes", "uniquely-named")
    assert wp.resolve_wiki(tmp_path, "uniquely-named") == p


def test_resolve_wiki_by_slug_ambiguous_raises(tmp_path: Path):
    _make_wiki(tmp_path, "concepts", "shared")
    _make_wiki(tmp_path, "notes", "shared")
    with pytest.raises(PKMValidationError):
        wp.resolve_wiki(tmp_path, "shared")


def test_resolve_wiki_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        wp.resolve_wiki(tmp_path, "does-not-exist")


def test_iter_all_wiki(tmp_path: Path):
    _make_wiki(tmp_path, "concepts", "a")
    _make_wiki(tmp_path, "concepts", "b")
    _make_wiki(tmp_path, "notes", "c")
    out = sorted(p.name for p in wp.iter_all_wiki(tmp_path))
    assert out == ["a.md", "b.md", "c.md"]
```

- [ ] **Step 4.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_wiki_paths.py -v
```

Expected: 8 fails (`ModuleNotFoundError: No module named 'pkm.store.wiki_paths'`).

- [ ] **Step 4.3: Implement `pkm/store/wiki_paths.py`**

```python
"""Wiki path helpers shared by promote / demote / wiki edit / lint.

`WIKI_BUCKETS` is owned by `pkm.store.frontmatter_schemas` (the schema
module is the single source of truth). We re-export it here so callers
that already think in path terms (`promote.py`, `demote.py`, etc.) don't
need to reach into the schemas module.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError, PKMValidationError
from pkm.store.frontmatter_schemas import WIKI_BUCKETS  # re-export

__all__ = [
    "WIKI_BUCKETS",
    "wiki_dir",
    "wiki_path",
    "iter_all_wiki",
    "resolve_wiki",
]


def wiki_dir(root: Path, bucket: str) -> Path:
    """Return the directory for a wiki bucket. Does not validate existence."""
    return root / "data" / "wiki" / bucket


def wiki_path(root: Path, bucket: str, slug: str) -> Path:
    """Return the canonical path for a wiki page (without checking existence)."""
    return wiki_dir(root, bucket) / f"{slug}.md"


def iter_all_wiki(root: Path) -> Iterator[Path]:
    """Yield every wiki .md file under data/wiki/<bucket>/."""
    base = root / "data" / "wiki"
    if not base.exists():
        return
    for bucket in WIKI_BUCKETS:
        d = base / bucket
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            yield p


def resolve_wiki(root: Path, ref: str) -> Path:
    """Resolve a user-supplied wiki reference to a Path.

    Accepted forms:
      1. Full path: 'data/wiki/<bucket>/<slug>.md'
      2. Bucket/slug shorthand: '<bucket>/<slug>'
      3. Bare slug: '<slug>' — must be unique across all buckets

    Raises PKMNotFoundError if nothing matches, PKMValidationError if a
    bare slug is ambiguous across buckets.
    """
    # Form 1: path-like
    if "/" in ref and ref.endswith(".md"):
        p = (root / ref).resolve()
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(
            f"wiki page not found: {ref}",
            hint=f"Expected under data/wiki/<bucket>/. Buckets: {', '.join(WIKI_BUCKETS)}",
        )

    # Form 2: <bucket>/<slug>
    if "/" in ref:
        bucket, slug = ref.split("/", 1)
        if bucket in WIKI_BUCKETS:
            p = wiki_path(root, bucket, slug)
            if p.exists():
                return p
            raise PKMNotFoundError(
                f"wiki page not found: {bucket}/{slug}",
                hint=f"Try `ls data/wiki/{bucket}/`",
            )

    # Form 3: bare slug
    matches = [p for p in iter_all_wiki(root) if p.stem == ref]
    if not matches:
        raise PKMNotFoundError(
            f"no wiki page named {ref!r}",
            hint=f"Buckets: {', '.join(WIKI_BUCKETS)}. Try `pkm search {ref}`.",
        )
    if len(matches) > 1:
        names = ", ".join(p.relative_to(root).as_posix() for p in matches)
        raise PKMValidationError(
            f"wiki ref {ref!r} is ambiguous: {names}",
            hint="Pass <bucket>/<slug> or full path.",
        )
    return matches[0]
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_wiki_paths.py -v
```

Expected: 8 passes.

- [ ] **Step 4.5: Commit**

```bash
git add pkm/store/wiki_paths.py tests/test_wiki_paths.py
git commit -m "$(cat <<'EOF'
M4.4: pkm.store.wiki_paths — bucket/slug ↔ path helpers

WIKI_BUCKETS, wiki_dir, wiki_path, iter_all_wiki, resolve_wiki.
Three resolution forms: full path, bucket/slug, bare slug (must be
unambiguous). Shared by promote/demote/wiki edit/lint.
EOF
)"
```

---

### Task 5: `pkm wiki edit --replace` (TDD)

**Files:**
- Create: `pkm/commands/wiki.py`, `tests/test_wiki_edit_replace.py`
- Modify: `pkm/cli.py` (register the wiki subgroup)

**Goal:** `pkm wiki edit <ref> --replace` reads stdin as the entire file content (frontmatter + body), validates the frontmatter against `validate_wiki`, validates wikilinks (every `[[x]]` resolves to an existing wiki slug), and atomically writes the file. Goes through `post_mutation` so reindex + git commit happen.

This is the strict-mode escape valve (spec §4.3). `Write(./data/wiki/**)` is denied at the .claude/settings.json layer; `pkm wiki edit` is the only authorized path. The CLI itself doesn't enforce strict mode — Claude's permissions do — but the validation here ensures whatever lands in the file is well-formed.

#### Steps

- [ ] **Step 5.1: Write failing tests `tests/test_wiki_edit_replace.py`**

```python
"""Tests for `pkm wiki edit --replace`."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Seed one wiki page directly (this is what promote will normally do)
    target = tmp_path / "data" / "wiki" / "concepts" / "oauth.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        "title: OAuth\n"
        "slug: oauth\n"
        "bucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\n"
        "lang: ko\n"
        "tags: []\n"
        "---\n"
        "Original body.\n",
        encoding="utf-8",
    )
    # Track it in git so promote/demote/edit chains see a clean tree
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wiki"], cwd=tmp_path, check=True)
    return tmp_path


REPLACEMENT = (
    "---\n"
    "title: OAuth\n"
    "slug: oauth\n"
    "bucket: concepts\n"
    "created_at: 2026-05-01T10:00:00+09:00\n"
    "updated_at: 2026-05-02T11:00:00+09:00\n"
    "status: active\n"
    "lang: ko\n"
    "tags: [auth]\n"
    "---\n"
    "Updated body. See [[csrf]] for related.\n"
)


def test_wiki_edit_replace_writes_and_returns_sha(initialized_repo: Path):
    # Seed the wikilink target so [[csrf]] resolves
    csrf = initialized_repo / "data" / "wiki" / "concepts" / "csrf.md"
    csrf.write_text(
        "---\ntitle: CSRF\nslug: csrf\nbucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\nlang: ko\ntags: []\n---\nstub\n",
        encoding="utf-8",
    )
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=initialized_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add csrf"], cwd=initialized_repo, check=True)

    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--replace",
              "--root", str(initialized_repo), "--json"],
        input=REPLACEMENT,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["path"] == "data/wiki/concepts/oauth.md"
    assert payload["git_commit"] is not None
    body = (initialized_repo / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "Updated body." in body
    assert "[[csrf]]" in body


def test_wiki_edit_replace_rejects_missing_required_frontmatter(initialized_repo: Path):
    bad = "---\ntitle: x\n---\nbody\n"
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--replace",
              "--root", str(initialized_repo), "--json"],
        input=bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_wiki_edit_replace_rejects_broken_wikilink(initialized_repo: Path):
    body_with_bad = REPLACEMENT.replace("[[csrf]]", "[[does-not-exist]]")
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--replace",
              "--root", str(initialized_repo), "--json"],
        input=body_with_bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "BROKEN_WIKILINK" in payload["error"]["code"] or "does-not-exist" in payload["error"]["message"]


def test_wiki_edit_replace_unknown_ref(initialized_repo: Path):
    result = runner.invoke(
        app, ["wiki", "edit", "missing-slug", "--replace",
              "--root", str(initialized_repo), "--json"],
        input=REPLACEMENT,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_wiki_edit_replace_disallows_changing_slug(initialized_repo: Path):
    # The path's slug is "oauth" but the new frontmatter says "renamed"
    bad = REPLACEMENT.replace("slug: oauth", "slug: renamed")
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--replace",
              "--root", str(initialized_repo), "--json"],
        input=bad,
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 5.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_wiki_edit_replace.py -v
```

Expected: 5 fails (no `wiki` command).

- [ ] **Step 5.3: Implement `pkm/commands/wiki.py`**

```python
"""`pkm wiki ...` — strict-mode escape valve commands.

M4 ships only `wiki edit`. Future `wiki list/show/rm` etc. land here.

Spec reference: §3.2 (wiki edit), §4.3 (escape valve), §6.1 (schema).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMValidationError
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import validate_wiki
from pkm.store.log import LogEvent
from pkm.store.wiki_paths import iter_all_wiki, resolve_wiki

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def _all_wiki_slugs(root: Path) -> set[str]:
    return {p.stem for p in iter_all_wiki(root)}


def _check_wikilinks(body: str, known_slugs: set[str]) -> None:
    """Raise PKMValidationError if body contains [[x]] for an unknown slug.

    Slug match is case-sensitive and exact. The check happens against the
    set of all wiki slugs across all buckets — wikilinks don't carry bucket.
    """
    broken = [m for m in _WIKILINK_RE.findall(body) if m not in known_slugs]
    if broken:
        raise PKMValidationError(
            f"broken wikilink(s): {', '.join(sorted(set(broken)))}",
            hint="Each [[x]] must match an existing wiki page slug.",
        )
        # NB: lint codes this BROKEN_WIKILINK; the CLI error code stays
        # VALIDATION_ERROR per the global error contract.


def _replace(root: Path, target: Path, raw_text: str) -> dict:
    fm, body = parse(raw_text)  # raises PKMValidationError on malformed
    validate_wiki(fm)
    # The slug in frontmatter must match the file stem — wiki edit can't rename
    if fm.get("slug") != target.stem:
        raise PKMValidationError(
            f"frontmatter slug={fm.get('slug')!r} does not match file stem={target.stem!r}",
            hint="`wiki edit` cannot rename a page. Use demote → re-promote with --slug.",
        )
    # Wikilink validation against current world state. The page being edited
    # is allowed to self-reference itself.
    known = _all_wiki_slugs(root)
    _check_wikilinks(body, known)
    atomic_write(target, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="wiki.edit", ref=fm["slug"], message="replace"),
        paths=[str(target.relative_to(root))],
    )
    return {
        "ok": True,
        "path": target.relative_to(root).as_posix(),
        "slug": fm["slug"],
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    wiki_app = typer.Typer(name="wiki", help="Wiki escape-valve commands.", no_args_is_help=True)
    app.add_typer(wiki_app, name="wiki")

    @wiki_app.command("edit")
    def edit_cmd(
        ref: str = typer.Argument(..., help="Wiki page (full path, bucket/slug, or unique slug)."),
        replace: bool = typer.Option(False, "--replace", help="Read stdin as the full file content."),
        patch: bool = typer.Option(False, "--patch", help="Read stdin as a unified diff."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Edit a wiki page (escape valve for strict mode)."""
        if replace == patch:
            typer.echo("Error: pass exactly one of --replace or --patch.", err=True)
            raise typer.Exit(code=1)
        try:
            target = resolve_wiki(root, ref)
            stdin = sys.stdin.read()
            if replace:
                result = _replace(root, target, stdin)
            else:
                # --patch — implemented in Task 6
                from pkm.commands.wiki_patch import _patch
                result = _patch(root, target, stdin)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None

        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"edited {result['path']}  (commit {result['git_commit'] or 'none'})")
```

- [ ] **Step 5.4: Register the wiki subgroup in `pkm/cli.py`**

Same pattern as Task 2. Add the import + register call:

```python
from pkm.commands import wiki as wiki_cmd  # noqa: F401
# ...
wiki_cmd.register(app)
```

- [ ] **Step 5.5: Stub `pkm/commands/wiki_patch.py` so import works**

`wiki.py` imports `wiki_patch._patch` lazily, but the module needs to exist now (or use a try/except). For TDD cleanliness, create a placeholder:

```python
"""Placeholder — implemented in Task 6."""
from __future__ import annotations
from pathlib import Path

from pkm.errors import PKMError


def _patch(root: Path, target: Path, raw_text: str) -> dict:
    raise PKMError("--patch not yet implemented (Task 6)")
```

(Task 6 will overwrite this file.)

- [ ] **Step 5.6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_wiki_edit_replace.py -v
```

Expected: 5 passes.

- [ ] **Step 5.7: Commit**

```bash
git add pkm/commands/wiki.py pkm/commands/wiki_patch.py pkm/cli.py tests/test_wiki_edit_replace.py
git commit -m "$(cat <<'EOF'
M4.5: pkm wiki edit --replace — strict-mode escape valve

stdin → full file content. Validates frontmatter against validate_wiki +
checks every [[x]] resolves to an existing wiki slug. Goes through
post_mutation so reindex + git commit happen. Slug rename is rejected
(frontmatter slug must match file stem). --patch stubbed for Task 6.
EOF
)"
```

---

### Task 6: `pkm wiki edit --patch` (TDD)

**Files:**
- Replace: `pkm/commands/wiki_patch.py`
- Create: `tests/test_wiki_edit_patch.py`

**Goal:** `pkm wiki edit <ref> --patch` reads stdin as a unified diff, applies via `git apply` to the working tree, validates the resulting file (same gate as `--replace`), then chains `post_mutation`. If the patch fails to apply or validation fails after applying, revert the working-tree change with `git checkout HEAD -- <path>` and surface the error.

The patch's diff header paths (`a/data/wiki/...` and `b/data/wiki/...`) MUST match the resolved target's relative path. We don't try to be clever about path remapping.

#### Steps

- [ ] **Step 6.1: Write failing tests `tests/test_wiki_edit_patch.py`**

```python
"""Tests for `pkm wiki edit --patch`."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_oauth(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    target = tmp_path / "data" / "wiki" / "concepts" / "oauth.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        "title: OAuth\n"
        "slug: oauth\n"
        "bucket: concepts\n"
        "created_at: 2026-05-01T10:00:00+09:00\n"
        "updated_at: 2026-05-01T10:00:00+09:00\n"
        "status: stub\n"
        "lang: ko\n"
        "tags: []\n"
        "---\n"
        "Original body.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed oauth"], cwd=tmp_path, check=True)
    return tmp_path


VALID_PATCH = """\
diff --git a/data/wiki/concepts/oauth.md b/data/wiki/concepts/oauth.md
--- a/data/wiki/concepts/oauth.md
+++ b/data/wiki/concepts/oauth.md
@@ -6,6 +6,6 @@ created_at: 2026-05-01T10:00:00+09:00
 updated_at: 2026-05-01T10:00:00+09:00
-status: stub
+status: active
 lang: ko
 tags: []
 ---
-Original body.
+Activated body.
"""


def test_wiki_edit_patch_applies_and_commits(repo_with_oauth: Path):
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=VALID_PATCH,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["git_commit"] is not None
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "Activated body." in body
    assert "status: active" in body


def test_wiki_edit_patch_invalid_diff_reverts(repo_with_oauth: Path):
    bad_patch = "this is not a unified diff at all"
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=bad_patch,
    )
    assert result.exit_code == 1
    # Working tree should still match the original
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "Original body." in body


def test_wiki_edit_patch_validation_failure_reverts(repo_with_oauth: Path):
    # A patch that applies fine but produces invalid frontmatter (bad enum)
    bad_patch = """\
diff --git a/data/wiki/concepts/oauth.md b/data/wiki/concepts/oauth.md
--- a/data/wiki/concepts/oauth.md
+++ b/data/wiki/concepts/oauth.md
@@ -6,3 +6,3 @@ created_at: 2026-05-01T10:00:00+09:00
 updated_at: 2026-05-01T10:00:00+09:00
-status: stub
+status: bogus
 lang: ko
"""
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input=bad_patch,
    )
    assert result.exit_code == 1
    body = (repo_with_oauth / "data" / "wiki" / "concepts" / "oauth.md").read_text(encoding="utf-8")
    assert "status: stub" in body  # reverted


def test_wiki_edit_patch_no_op_returns_null_commit(repo_with_oauth: Path):
    # An empty patch: no-op. The CLI should report success but git_commit=None.
    result = runner.invoke(
        app, ["wiki", "edit", "concepts/oauth", "--patch",
              "--root", str(repo_with_oauth), "--json"],
        input="",
    )
    # Empty stdin → git apply fails → exit 1 (we don't model this as success)
    assert result.exit_code == 1
```

- [ ] **Step 6.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_wiki_edit_patch.py -v
```

Expected: 4 fails (`PKMError: --patch not yet implemented`).

- [ ] **Step 6.3: Replace `pkm/commands/wiki_patch.py` with the real implementation**

```python
"""`pkm wiki edit --patch` — apply unified diff via git apply.

Strategy:
  1. `git apply --check` against stdin to dry-run the patch.
  2. If check passes, `git apply` to actually modify the working tree.
  3. Read the file back, validate frontmatter + wikilinks (same gate as
     --replace). On failure, `git checkout HEAD -- <path>` to revert.
  4. Chain post_mutation, which will commit the modified file.

Spec §3.2 (wiki edit --patch). Master spec uses `git apply` deliberately —
unified diff is the lingua franca and `git apply` is already a dep
(M3.5).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMValidationError
from pkm.store.frontmatter import parse
from pkm.store.frontmatter_schemas import validate_wiki
from pkm.store.log import LogEvent

# Reuse the wikilink check from commands/wiki.py to avoid duplication
from pkm.commands.wiki import _all_wiki_slugs, _check_wikilinks


def _git(args: list[str], *, cwd: Path, check: bool, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, input=stdin, check=check, capture_output=True, text=True,
    )


def _patch(root: Path, target: Path, raw_diff: str) -> dict:
    if not raw_diff.strip():
        raise PKMValidationError("empty patch", hint="stdin must contain a unified diff.")

    # 1. Dry-run via git apply --check
    check = _git(["git", "apply", "--check"], cwd=root, check=False, stdin=raw_diff)
    if check.returncode != 0:
        raise PKMValidationError(
            f"patch does not apply cleanly: {check.stderr.strip() or 'unknown error'}",
            hint="Confirm the diff was generated against the current file.",
        )

    # 2. Real apply
    apply = _git(["git", "apply"], cwd=root, check=False, stdin=raw_diff)
    if apply.returncode != 0:
        raise PKMError(f"git apply failed unexpectedly: {apply.stderr.strip()}")

    # 3. Validate post-apply
    try:
        text = target.read_text(encoding="utf-8")
        fm, body = parse(text)
        validate_wiki(fm)
        if fm.get("slug") != target.stem:
            raise PKMValidationError(
                f"frontmatter slug={fm.get('slug')!r} does not match file stem={target.stem!r}",
            )
        _check_wikilinks(body, _all_wiki_slugs(root))
    except PKMError:
        # Revert the working tree before re-raising
        rel = str(target.relative_to(root))
        _git(["git", "checkout", "HEAD", "--", rel], cwd=root, check=False)
        raise

    # 4. post_mutation chains log + reindex + git commit
    sha = post_mutation(
        root,
        LogEvent(type="wiki.edit", ref=fm["slug"], message="patch"),
        paths=[str(target.relative_to(root))],
    )
    return {
        "ok": True,
        "path": target.relative_to(root).as_posix(),
        "slug": fm["slug"],
        "git_commit": sha,
    }
```

- [ ] **Step 6.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_wiki_edit_patch.py tests/test_wiki_edit_replace.py -v
```

Expected: 9 passes total (4 patch + 5 replace).

- [ ] **Step 6.5: Commit**

```bash
git add pkm/commands/wiki_patch.py tests/test_wiki_edit_patch.py
git commit -m "$(cat <<'EOF'
M4.6: pkm wiki edit --patch — unified diff via git apply

git apply --check (dry-run) → git apply → validate → revert on failure
→ post_mutation. Reuses --replace's frontmatter+wikilink gate.
EOF
)"
```

---

### Task 7: `pkm promote` (capture → wiki) (TDD)

**Files:**
- Create: `pkm/commands/promote.py`, `tests/test_promote.py`
- Modify: `pkm/cli.py`

**Goal:** `pkm promote <ref> --to <bucket> [--slug NEW] [--keep-source]`. Resolves a capture by ref (existing M2 helper), checks gate (`status == reviewed` + capture frontmatter validates), copies to `data/wiki/<bucket>/<slug>.md` with a fresh `wiki_defaults` frontmatter (carrying `promoted_from: <source rel path>`), sets source `status: archived` (unless `--keep-source`), goes through `post_mutation` with both source and dest paths.

Writing input → returns code `PROMOTE_FROM_WRITING_NOT_YET` (M5 implements that branch).

#### Steps

- [ ] **Step 7.1: Write failing tests `tests/test_promote.py`**

```python
"""Tests for `pkm promote`."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_capture(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app,
        ["capture", "create", "--slug", "oauth-token-storage",
         "--title", "OAuth Token Storage", "--lang", "ko",
         "--root", str(tmp_path)],
        input="Body of the OAuth capture.\n",
    )
    return tmp_path


def _set_status_reviewed(repo: Path, slug_substr: str) -> None:
    runner.invoke(app, ["capture", "set-status", slug_substr, "reviewed",
                        "--root", str(repo)])


def test_promote_happy_path(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    # Default slug = capture slug stripped of date prefix
    assert payload["wiki_path"].startswith("data/wiki/concepts/")
    assert payload["wiki_path"].endswith("oauth-token-storage.md")
    assert payload["git_commit"] is not None

    # Wiki file exists with expected frontmatter
    wiki = repo_with_capture / payload["wiki_path"]
    text = wiki.read_text(encoding="utf-8")
    assert "bucket: concepts" in text
    assert "status: stub" in text
    assert "promoted_from: data/raw/captures/" in text

    # Capture status flipped to archived
    cap_dir = repo_with_capture / "data" / "raw" / "captures"
    cap_files = list(cap_dir.glob("*oauth-token-storage*.md"))
    assert len(cap_files) == 1
    assert "status: archived" in cap_files[0].read_text(encoding="utf-8")


def test_promote_rejects_draft_status(repo_with_capture: Path):
    # Source is still draft (we didn't mark it reviewed)
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "STATUS_NOT_REVIEWED"


def test_promote_unknown_bucket(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "garbage",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_promote_keep_source(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--keep-source",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0
    cap_files = list((repo_with_capture / "data" / "raw" / "captures").glob("*oauth*.md"))
    assert "status: reviewed" in cap_files[0].read_text(encoding="utf-8")


def test_promote_with_custom_slug(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "notes",
              "--slug", "ots-summary",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["wiki_path"].endswith("notes/ots-summary.md")


def test_promote_collision_existing_wiki_path(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    # Pre-create a wiki file at the destination
    target = repo_with_capture / "data" / "wiki" / "concepts" / "oauth-token-storage.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntitle: x\nslug: oauth-token-storage\nbucket: concepts\n"
                       "created_at: 2026-05-01T10:00:00+09:00\n"
                       "updated_at: 2026-05-01T10:00:00+09:00\n"
                       "status: stub\nlang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_with_capture, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wiki"], cwd=repo_with_capture, check=True)

    result = runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "STATE_ERROR"


def test_promote_writing_input_returns_carve_error(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Manually drop a writing file (write new is M5)
    w = tmp_path / "data" / "writing" / "x.md"
    w.write_text("---\ntitle: t\nslug: x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: final\npurpose: report\n"
                  "derived_from: [data/wiki/concepts/y.md]\n"
                  "lang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed writing"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["promote", "data/writing/x.md", "--to", "concepts",
              "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "PROMOTE_FROM_WRITING_NOT_YET"


def test_promote_chunk_input_rejected(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(app, ["chunks", "new", "oauth-deep-dive", "--root", str(tmp_path)])
    result = runner.invoke(
        app, ["promote", "data/raw/chunks/oauth-deep-dive", "--to", "concepts",
              "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_promote_emits_event(repo_with_capture: Path):
    _set_status_reviewed(repo_with_capture, "oauth-token-storage")
    runner.invoke(
        app, ["promote", "oauth-token-storage", "--to", "concepts",
              "--root", str(repo_with_capture)],
    )
    log = (repo_with_capture / "data" / "log.md").read_text(encoding="utf-8")
    assert "capture.promote" in log
```

- [ ] **Step 7.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_promote.py -v
```

Expected: 8 fails (no `promote` command).

- [ ] **Step 7.3: Add a new error code class for the M5 carve-out**

In `pkm/errors.py`, append after `PKMNotFoundError`:

```python
class PKMNotImplementedError(PKMError):
    """Code path is reserved for a future milestone."""
    code = "NOT_IMPLEMENTED"


class PKMStatusError(PKMError):
    """A status-transition gate failed (e.g. promote requires reviewed)."""
    code = "STATUS_NOT_REVIEWED"
```

(Reusing PKMStateError vs adding a specific code is a judgment call; the spec §6.3 example uses `STATUS_NOT_REVIEWED` as a stable code so we put it on its own subclass.)

For the writing carve-out, define a more specific subclass:

```python
class PKMPromoteFromWritingNotYet(PKMNotImplementedError):
    code = "PROMOTE_FROM_WRITING_NOT_YET"
```

- [ ] **Step 7.4: Implement `pkm/commands/promote.py`**

```python
"""`pkm promote <ref> --to <bucket>` — capture → wiki.

M4 handles the capture branch only. Writing branch returns
PROMOTE_FROM_WRITING_NOT_YET (M5 fills in).

Spec reference: §6.3 (gate), §6.6 (auto side-effects).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import (
    PKMError,
    PKMPromoteFromWritingNotYet,
    PKMStateError,
    PKMStatusError,
    PKMValidationError,
)
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import (
    validate_capture,
    validate_wiki,
    wiki_defaults,
)
from pkm.store.log import LogEvent
from pkm.store.refs import resolve_capture
from pkm.store.wiki_paths import WIKI_BUCKETS, wiki_path

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _strip_date_prefix(slug: str) -> str:
    return _DATE_PREFIX_RE.sub("", slug, count=1)


def _do_promote(
    root: Path,
    *,
    ref: str,
    bucket: str,
    new_slug: str | None,
    keep_source: bool,
) -> dict:
    if bucket not in WIKI_BUCKETS:
        raise PKMValidationError(
            f"unknown bucket {bucket!r}",
            hint=f"Valid buckets: {', '.join(WIKI_BUCKETS)}.",
        )

    # Reject writing input early (M5 carve-out)
    if ref.startswith("data/writing/") or ref.startswith("writing/"):
        raise PKMPromoteFromWritingNotYet(
            "promoting from data/writing/ lands in M5 alongside `pkm write new`",
            hint="For now, promote a capture instead, or wait for M5.",
        )
    # Reject chunk dirs explicitly (spec §6.3 says chunks → AI synthesis route)
    if ref.startswith("data/raw/chunks/") or ref.startswith("chunks/"):
        raise PKMValidationError(
            "cannot promote a chunks topic directly",
            hint="See SCHEMA.md → Chunk → Wiki Synthesis. Synthesize a writing/ file first.",
        )

    # Resolve the capture
    src = resolve_capture(root, ref)  # raises PKMNotFoundError / Validation (ambiguous)
    fm_src, body_src = parse(src.read_text(encoding="utf-8"))
    validate_capture(fm_src)

    if fm_src.get("status") != "reviewed":
        raise PKMStatusError(
            f"capture status is {fm_src.get('status')!r}, must be 'reviewed'",
            hint=f"Run: pkm capture set-status {fm_src['slug']} reviewed",
        )

    # Choose destination slug
    dst_slug = new_slug if new_slug is not None else _strip_date_prefix(fm_src["slug"])
    dst = wiki_path(root, bucket, dst_slug)
    if dst.exists():
        raise PKMStateError(
            f"wiki page already exists at {dst.relative_to(root)}",
            hint=f"Pick a different --slug, or `pkm wiki edit` the existing page.",
        )

    # Build wiki frontmatter (carries provenance)
    fm_dst = wiki_defaults(
        slug=dst_slug,
        title=fm_src.get("title", dst_slug),
        bucket=bucket,
        status="stub",
        lang=fm_src.get("lang", "ko"),
        tags=fm_src.get("tags") or [],
        promoted_from=str(src.relative_to(root)),
    )
    validate_wiki(fm_dst)

    # Write wiki file
    atomic_write(dst, serialize(fm_dst, body_src))

    # Update source status (unless --keep-source)
    paths = [str(dst.relative_to(root))]
    if not keep_source:
        fm_src["status"] = "archived"
        validate_capture(fm_src)
        atomic_write(src, serialize(fm_src, body_src))
        paths.append(str(src.relative_to(root)))

    sha = post_mutation(
        root,
        LogEvent(type="capture.promote",
                 ref=fm_src["slug"],
                 message=f"→ {bucket}/{dst_slug}"),
        paths=paths,
    )
    return {
        "ok": True,
        "wiki_path": dst.relative_to(root).as_posix(),
        "wiki_slug": dst_slug,
        "source_path": src.relative_to(root).as_posix(),
        "source_archived": not keep_source,
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    @app.command("promote")
    def promote_cmd(
        ref: str = typer.Argument(..., help="Capture ref (slug, full slug, or path)."),
        to: str = typer.Option(..., "--to", help="Wiki bucket: concepts | entities | notes | reports."),
        slug: str | None = typer.Option(None, "--slug", help="Override the wiki slug (default: capture slug minus date prefix)."),
        keep_source: bool = typer.Option(False, "--keep-source", help="Don't archive the source capture."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Promote a reviewed capture into a wiki bucket."""
        try:
            result = _do_promote(root, ref=ref, bucket=to, new_slug=slug, keep_source=keep_source)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(
                f"promoted {result['source_path']} → {result['wiki_path']}"
                + (" (source kept)" if not result["source_archived"] else " (source archived)")
            )
```

- [ ] **Step 7.5: Register in `pkm/cli.py`**

Same import + register pattern.

- [ ] **Step 7.6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_promote.py -v
```

Expected: 8 passes. (If `test_promote_collision_existing_wiki_path` fails on git state — the `runner.invoke(... init ...)` already creates an initial commit; the manual file + commit in the test starts from that.)

- [ ] **Step 7.7: Commit**

```bash
git add pkm/errors.py pkm/commands/promote.py pkm/cli.py tests/test_promote.py
git commit -m "$(cat <<'EOF'
M4.7: pkm promote <ref> --to <bucket> — capture → wiki

Gate: status==reviewed + validate_capture + bucket in WIKI_BUCKETS.
Default dest slug strips the date prefix; --slug overrides; --keep-source
keeps source as-is. Source flips to archived otherwise. Writing/chunks
input return stable error codes (PROMOTE_FROM_WRITING_NOT_YET / VALIDATION_ERROR).
post_mutation chains both source and destination paths.
EOF
)"
```

---

### Task 8: `pkm demote` (wiki → capture) (TDD)

**Files:**
- Create: `pkm/commands/demote.py`, `tests/test_demote.py`
- Modify: `pkm/cli.py`

**Goal:** `pkm demote <wiki-ref> [--target PATH]`. Reads wiki frontmatter; if `promoted_from: data/raw/captures/...` is present, restore the source capture to `status: reviewed` (if it still exists) and delete the wiki file. If `promoted_from` is missing or points to a path that no longer exists and no `--target` is given, error out.

M4 only handles the capture-origin case. Writing-origin demote (when `promoted_from: data/writing/...`) is M5.

#### Steps

- [ ] **Step 8.1: Write failing tests `tests/test_demote.py`**

```python
"""Tests for `pkm demote`."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_promoted(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app,
        ["capture", "create", "--slug", "csrf",
         "--title", "CSRF", "--lang", "ko",
         "--root", str(tmp_path)],
        input="csrf body\n",
    )
    runner.invoke(app, ["capture", "set-status", "csrf", "reviewed", "--root", str(tmp_path)])
    runner.invoke(app, ["promote", "csrf", "--to", "concepts", "--root", str(tmp_path)])
    return tmp_path


def test_demote_round_trips_to_reviewed(repo_with_promoted: Path):
    result = runner.invoke(
        app, ["demote", "concepts/csrf", "--root", str(repo_with_promoted), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    # Wiki file gone
    assert not (repo_with_promoted / "data" / "wiki" / "concepts" / "csrf.md").exists()
    # Source capture restored to status=reviewed
    cap = next((repo_with_promoted / "data" / "raw" / "captures").glob("*csrf*.md"))
    assert "status: reviewed" in cap.read_text(encoding="utf-8")


def test_demote_missing_promoted_from(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    # Hand-author a wiki page without promoted_from
    p = tmp_path / "data" / "wiki" / "concepts" / "orphan.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Orphan\nslug: orphan\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n---\nbody\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed orphan"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["demote", "concepts/orphan", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] in ("STATE_ERROR", "VALIDATION_ERROR")


def test_demote_writing_origin_returns_carve_error(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / "data" / "wiki" / "concepts" / "writing-origin.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: WO\nslug: writing-origin\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n"
                  "promoted_from: data/writing/some.md\n---\nbody\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed wo"], cwd=tmp_path, check=True)

    result = runner.invoke(
        app, ["demote", "concepts/writing-origin", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "DEMOTE_TO_WRITING_NOT_YET"


def test_demote_unknown_wiki_ref(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    result = runner.invoke(
        app, ["demote", "concepts/nope", "--root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "NOT_FOUND"


def test_demote_emits_event(repo_with_promoted: Path):
    runner.invoke(app, ["demote", "concepts/csrf", "--root", str(repo_with_promoted)])
    log = (repo_with_promoted / "data" / "log.md").read_text(encoding="utf-8")
    assert "wiki.demote" in log
```

- [ ] **Step 8.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_demote.py -v
```

Expected: 5 fails (no `demote` command).

- [ ] **Step 8.3: Add the M5 carve-out error code**

In `pkm/errors.py`:

```python
class PKMDemoteToWritingNotYet(PKMNotImplementedError):
    code = "DEMOTE_TO_WRITING_NOT_YET"
```

- [ ] **Step 8.4: Implement `pkm/commands/demote.py`**

```python
"""`pkm demote <wiki-ref>` — wiki → capture (or writing in M5).

If the wiki page has `promoted_from: data/raw/captures/...`, restore that
capture to status=reviewed and delete the wiki file. Writing-origin pages
return DEMOTE_TO_WRITING_NOT_YET (M5).

Spec reference: §6.4 (demote).
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import (
    PKMDemoteToWritingNotYet,
    PKMError,
    PKMStateError,
)
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import validate_capture
from pkm.store.log import LogEvent
from pkm.store.wiki_paths import resolve_wiki


def _do_demote(root: Path, *, ref: str) -> dict:
    wiki_p = resolve_wiki(root, ref)
    fm_w, _body_w = parse(wiki_p.read_text(encoding="utf-8"))
    promoted_from = fm_w.get("promoted_from")
    if not promoted_from:
        raise PKMStateError(
            f"wiki page {wiki_p.relative_to(root)} has no `promoted_from`",
            hint="V1 demote only handles capture-origin pages with provenance.",
        )

    if promoted_from.startswith("data/writing/"):
        raise PKMDemoteToWritingNotYet(
            "demoting writing-origin pages lands in M5 alongside `pkm write new`",
            hint="Delete by hand or wait for M5.",
        )

    src_p = root / promoted_from
    if not src_p.exists():
        raise PKMStateError(
            f"`promoted_from` source missing: {promoted_from}",
            hint="The original capture was deleted. Recreate it or remove the wiki page manually.",
        )

    # Restore source status: archived → reviewed
    fm_s, body_s = parse(src_p.read_text(encoding="utf-8"))
    fm_s["status"] = "reviewed"
    validate_capture(fm_s)
    atomic_write(src_p, serialize(fm_s, body_s))

    # Delete wiki file
    wiki_rel = str(wiki_p.relative_to(root))
    wiki_p.unlink()

    sha = post_mutation(
        root,
        LogEvent(type="wiki.demote",
                 ref=fm_w.get("slug", wiki_p.stem),
                 message=f"← restored {fm_s['slug']}"),
        paths=[wiki_rel, str(src_p.relative_to(root))],
    )
    return {
        "ok": True,
        "wiki_path": wiki_rel,
        "source_path": src_p.relative_to(root).as_posix(),
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    @app.command("demote")
    def demote_cmd(
        ref: str = typer.Argument(..., help="Wiki ref (full path, bucket/slug, or unique slug)."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Demote a wiki page back to its source capture (status: reviewed)."""
        try:
            result = _do_demote(root, ref=ref)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(
                f"demoted {result['wiki_path']} → restored {result['source_path']} (status: reviewed)"
            )
```

- [ ] **Step 8.5: Register in `pkm/cli.py`**

- [ ] **Step 8.6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_demote.py -v
```

Expected: 5 passes.

- [ ] **Step 8.7: Commit**

```bash
git add pkm/errors.py pkm/commands/demote.py pkm/cli.py tests/test_demote.py
git commit -m "$(cat <<'EOF'
M4.8: pkm demote <wiki-ref> — wiki → capture round-trip

Reads promoted_from; restores source to status=reviewed; deletes wiki
file. Writing-origin returns DEMOTE_TO_WRITING_NOT_YET (M5). Missing
promoted_from or missing source → STATE_ERROR.
EOF
)"
```

---

### Task 9: Record `body_hash` on capture set-status reviewed (TDD)

**Files:**
- Modify: `pkm/commands/capture.py` (only `_do_set_status`)
- Create: `tests/test_capture_body_hash.py`

**Goal:** When a capture transitions into `reviewed` for the first time, compute `sha256(body)` and stash it in frontmatter as `body_hash`. The Task 10 `RAW_BODY_MUTATED` lint rule reads this field — without this wiring, real-world captures never carry a hash and the rule stays permanently dormant (the rule's unit test fakes the hash by hand to exercise detection).

The hash is set ONLY the first time the field is absent and the new status is `reviewed`. Subsequent transitions (reviewed→archived→reviewed) leave the existing hash untouched — it represents "the body as the user first committed to review". Captures created before M4 don't have the hash either; the lint rule skips them silently (consistent with the rule's docstring).

#### Steps

- [ ] **Step 9.1: Write failing tests `tests/test_capture_body_hash.py`**

```python
"""Tests that capture.set-status records body_hash on transition to reviewed."""
from __future__ import annotations
import hashlib
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init_with_capture(tmp_path: Path, body: str) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app, ["capture", "create", "--slug", "x", "--title", "X",
              "--lang", "ko", "--root", str(tmp_path)],
        input=body,
    )
    return tmp_path


def _cap_path(repo: Path) -> Path:
    return next((repo / "data" / "raw" / "captures").glob("*x*.md"))


def test_draft_capture_has_no_body_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "초안 본문\n")
    fm, _ = parse(_cap_path(repo).read_text(encoding="utf-8"))
    assert "body_hash" not in fm


def test_set_status_reviewed_writes_body_hash(tmp_path: Path):
    body = "한국어 본문\n"
    repo = _init_with_capture(tmp_path, body)
    runner.invoke(app, ["capture", "set-status", "x", "reviewed",
                        "--root", str(repo)])
    fm, parsed_body = parse(_cap_path(repo).read_text(encoding="utf-8"))
    assert fm.get("body_hash") == hashlib.sha256(parsed_body.encode("utf-8")).hexdigest()


def test_idempotent_set_reviewed_does_not_change_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "body\n")
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    cap = _cap_path(repo)
    first = parse(cap.read_text(encoding="utf-8"))[0]["body_hash"]
    # Mutate the body manually (simulating an out-of-band edit that the lint rule should catch)
    text = cap.read_text(encoding="utf-8")
    cap.write_text(text.replace("body\n", "body\n\nedited\n"), encoding="utf-8")
    # set-status reviewed again — must NOT recompute hash
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    fm, _ = parse(cap.read_text(encoding="utf-8"))
    assert fm["body_hash"] == first


def test_archived_then_reviewed_preserves_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "body\n")
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    cap = _cap_path(repo)
    first = parse(cap.read_text(encoding="utf-8"))[0]["body_hash"]
    runner.invoke(app, ["capture", "set-status", "x", "archived", "--root", str(repo)])
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    fm, _ = parse(cap.read_text(encoding="utf-8"))
    assert fm["body_hash"] == first
```

- [ ] **Step 9.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_capture_body_hash.py -v
```

Expected: 3 of 4 fail (the `draft has no hash` test passes trivially; the others fail because `body_hash` is never written).

- [ ] **Step 9.3: Modify `_do_set_status` in `pkm/commands/capture.py`**

Locate the existing `_do_set_status` function and add the hash logic. The current function signature stays unchanged — we only add 3 lines plus the import.

```python
import hashlib
# ... (existing imports)

def _do_set_status(root: Path, ref: str, status: str) -> dict:
    from pkm.store.frontmatter import parse
    from pkm.store.refs import resolve_capture
    p = resolve_capture(root, ref)
    fm, body = parse(p.read_text(encoding="utf-8"))
    fm["status"] = status
    if status == "reviewed" and "body_hash" not in fm:
        fm["body_hash"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    validate_capture(fm)  # raises PKMValidationError on bad enum
    atomic_write(p, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="capture.set-status", ref=fm["slug"], message=status),
        paths=[str(p.relative_to(root))],
    )
    return {"ok": True, "id": fm["slug"], "path": p.relative_to(root).as_posix(), "git_commit": sha}
```

The `body_hash not in fm` guard makes this idempotent: once set, the hash is never recomputed by `set-status`.

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_capture_body_hash.py tests/test_capture.py -v
```

Expected: 4 new tests pass + the existing M2 capture tests continue to pass. (The existing tests don't assert on `body_hash` so they're indifferent to the new field.)

- [ ] **Step 9.5: Commit**

```bash
git add pkm/commands/capture.py tests/test_capture_body_hash.py
git commit -m "$(cat <<'EOF'
M4.9: capture set-status reviewed records body_hash

Computes sha256(body) on the first transition into reviewed. Idempotent:
once present, set-status leaves the hash alone (so reviewed→archived→
reviewed preserves the original hash). Pre-M4 captures without the
field stay un-hashed; the M4.10 RAW_BODY_MUTATED lint rule skips them.
EOF
)"
```

---

### Task 10: `pkm/lint/rules.py` — 6 Errors + 7 Warnings (TDD)

**Files:**
- Create: `pkm/lint/__init__.py`, `pkm/lint/rules.py`
- Create: `tests/test_lint_errors.py`, `tests/test_lint_warnings.py`

**Goal:** 13 detection functions, all returning `LintFinding` records. Fully read-only — no mutation. The CLI in Task 12 will call `collect_findings(root) → list[LintFinding]` and render or fix.

**LintFinding shape:**
```python
@dataclass(frozen=True)
class LintFinding:
    code: str            # e.g. "MISSING_FIELD" / "BROKEN_WIKILINK"
    severity: str        # "error" | "warning"
    path: str            # data/raw/captures/2026-05-01-foo.md
    message: str
    field: str | None = None     # e.g. "title" for MISSING_FIELD
    fixable: bool = False
```

**Rule list:**

| Code | Severity | What it checks | Fixable in M4 |
|---|---|---|---|
| `MISSING_FIELD` | error | required frontmatter fields per kind | created_at, slug only |
| `INVALID_VALUE` | error | enum violations (status/lang/bucket/source_type/purpose) | no |
| `DUPLICATE_SLUG` | error | same slug twice within a bucket OR within captures | no |
| `BROKEN_WIKILINK` | error | `[[x]]` body refs that don't resolve to any wiki slug | no |
| `BROKEN_DERIVED_FROM` | error | `derived_from: [...]` paths that don't exist | no |
| `ORPHAN_PROMOTED_SOURCE` | error | wiki has `promoted_from: P`; P exists with status≠archived | yes (set source archived) |
| `STALE_DRAFT` | warning | capture status=draft, mtime > 30 days ago | no |
| `STALE_STUB` | warning | wiki status=stub, mtime > 30 days ago | no |
| `ORPHAN_WIKI` | warning | wiki page with no incoming wikilinks, no derived_from refs, and no tags | no |
| `LARGE_CHUNK_NEVER_PROMOTED` | warning | chunks status=ready, mtime > 60 days, no wiki page references it | no |
| `LANG_INCONSISTENT` | warning | declared `lang: ko` but body looks ASCII-only (or vice versa) | no |
| `RAW_BODY_MUTATED` | warning | capture status=reviewed, body hash differs from when it became reviewed (immutability) | no |
| `BROKEN_CITATION` | warning | wiki body has `[text](data/...)` link where the path doesn't exist | no |

`RAW_BODY_MUTATED` needs a "body hash at status transition" record. M4 stores this lazily: on first capture set-status reviewed, write `body_hash: <sha256>` to frontmatter. Then lint compares current body's hash to stored. Captures created before M4 won't have the hash → rule skips them with no finding (NOT a false positive).

**Implementation note:** all 13 rule functions take `(root: Path, all_files: WikiAndCaptureSnapshot) → Iterable[LintFinding]` where `WikiAndCaptureSnapshot` is a small dataclass holding pre-parsed (path, frontmatter, body) tuples for all wiki + capture + chunks + writing files. We parse once and pass around — avoids hammering the disk for each rule.

#### Steps

- [ ] **Step 10.1: Write failing tests `tests/test_lint_errors.py`**

```python
"""Tests for the 6 Error-severity lint rules."""
from __future__ import annotations
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _write(p: Path, fm_text: str, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def _commit(repo: Path) -> None:
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed test data"], cwd=repo, check=True)


def _codes(findings) -> list[str]:
    return sorted(f.code for f in findings)


def test_missing_field_capture(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
           "title: X\nslug: 2026-05-01-x\nstatus: draft\nlang: ko",  # missing created_at + source_type
           "body")
    _commit(repo)
    findings = list(collect_findings(repo))
    assert "MISSING_FIELD" in _codes(findings)


def test_invalid_value_status(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
           "title: X\nslug: 2026-05-01-x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
           "status: bogus\nsource_type: text\nlang: ko",
           "body")
    _commit(repo)
    assert "INVALID_VALUE" in _codes(collect_findings(repo))


def test_duplicate_slug_in_same_bucket(tmp_path: Path):
    repo = _init(tmp_path)
    base_fm = ("title: A\nslug: shared\nbucket: concepts\n"
               "created_at: 2026-05-01T10:00:00+09:00\n"
               "updated_at: 2026-05-01T10:00:00+09:00\n"
               "status: stub\nlang: ko\ntags: []")
    _write(repo / "data" / "wiki" / "concepts" / "shared.md", base_fm, "x")
    # Two files with same slug — rename file but slug field stays "shared"
    _write(repo / "data" / "wiki" / "concepts" / "alt.md",
           base_fm.replace("title: A", "title: B"), "y")
    _commit(repo)
    assert "DUPLICATE_SLUG" in _codes(collect_findings(repo))


def test_broken_wikilink(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "page.md",
           "title: P\nslug: page\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []",
           "See [[nonexistent]] for context.")
    _commit(repo)
    assert "BROKEN_WIKILINK" in _codes(collect_findings(repo))


def test_broken_derived_from(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "page.md",
           "title: P\nslug: page\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []\n"
           "derived_from: [data/wiki/concepts/missing.md]",
           "body")
    _commit(repo)
    assert "BROKEN_DERIVED_FROM" in _codes(collect_findings(repo))


def test_orphan_promoted_source(tmp_path: Path):
    repo = _init(tmp_path)
    # Capture status=reviewed (NOT archived), wiki has promoted_from pointing at it
    _write(repo / "data" / "raw" / "captures" / "2026-05-01-x.md",
           "title: X\nslug: 2026-05-01-x\ncreated_at: 2026-05-01T10:00:00+09:00\n"
           "status: reviewed\nsource_type: text\nlang: ko",
           "body")
    _write(repo / "data" / "wiki" / "concepts" / "x.md",
           "title: X\nslug: x\nbucket: concepts\n"
           "created_at: 2026-05-02T10:00:00+09:00\n"
           "updated_at: 2026-05-02T10:00:00+09:00\n"
           "status: stub\nlang: ko\ntags: []\n"
           "promoted_from: data/raw/captures/2026-05-01-x.md",
           "body")
    _commit(repo)
    codes = _codes(collect_findings(repo))
    assert "ORPHAN_PROMOTED_SOURCE" in codes
```

- [ ] **Step 10.2: Write failing tests `tests/test_lint_warnings.py`**

```python
"""Tests for the 7 Warning-severity lint rules."""
from __future__ import annotations
import os
import time
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _write(p: Path, fm_text: str, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def _backdate(p: Path, days: int) -> None:
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


def test_stale_draft(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-04-01-old.md"
    _write(p, "title: O\nslug: 2026-04-01-old\n"
              "created_at: 2026-04-01T10:00:00+09:00\n"
              "status: draft\nsource_type: text\nlang: ko", "body")
    _backdate(p, 31)
    assert "STALE_DRAFT" in _codes(collect_findings(repo))


def test_stale_stub(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "wiki" / "concepts" / "stale.md"
    _write(p, "title: S\nslug: stale\nbucket: concepts\n"
              "created_at: 2026-04-01T10:00:00+09:00\n"
              "updated_at: 2026-04-01T10:00:00+09:00\n"
              "status: stub\nlang: ko\ntags: []", "body")
    _backdate(p, 31)
    assert "STALE_STUB" in _codes(collect_findings(repo))


def test_orphan_wiki(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "lonely.md",
           "title: L\nslug: lonely\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []", "no incoming refs")
    assert "ORPHAN_WIKI" in _codes(collect_findings(repo))


def test_lang_inconsistent_ko_with_ascii_body(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-en.md"
    _write(p, "title: E\nslug: 2026-05-01-en\n"
              "created_at: 2026-05-01T10:00:00+09:00\n"
              "status: draft\nsource_type: text\nlang: ko",
           "This body has zero Korean. " * 10)
    assert "LANG_INCONSISTENT" in _codes(collect_findings(repo))


def test_broken_citation(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "p.md",
           "title: P\nslug: p\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []",
           "See [paper](data/raw/captures/missing.md) for details.")
    assert "BROKEN_CITATION" in _codes(collect_findings(repo))


def test_large_chunk_never_promoted(tmp_path: Path):
    repo = _init(tmp_path)
    chunk_dir = repo / "data" / "raw" / "chunks" / "old-topic"
    chunk_dir.mkdir(parents=True)
    readme = chunk_dir / "README.md"
    _write(readme, "topic: old-topic\n"
                   "created_at: 2026-03-01T10:00:00+09:00\n"
                   "status: ready\nlang: mixed\nsources: []", "body")
    _backdate(readme, 65)
    assert "LARGE_CHUNK_NEVER_PROMOTED" in _codes(collect_findings(repo))


def test_raw_body_mutated(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-m.md"
    # Capture has body_hash recorded but body is now different
    import hashlib
    stale_hash = hashlib.sha256(b"original body\n").hexdigest()
    _write(p, "title: M\nslug: 2026-05-01-m\n"
              "created_at: 2026-05-01T10:00:00+09:00\n"
              "status: reviewed\nsource_type: text\nlang: ko\n"
              f"body_hash: {stale_hash}",
           "DIFFERENT body now\n")
    assert "RAW_BODY_MUTATED" in _codes(collect_findings(repo))
```

- [ ] **Step 10.3: Run failing tests**

```bash
.venv/bin/pytest tests/test_lint_errors.py tests/test_lint_warnings.py -v
```

Expected: 13 fails (`ImportError: cannot import 'collect_findings' from 'pkm.lint'`).

- [ ] **Step 10.4: Implement `pkm/lint/__init__.py`**

```python
"""Lint engine. Detection in `rules.py`, auto-fix in `fixers.py`."""
from pkm.lint.rules import LintFinding, collect_findings

__all__ = ["LintFinding", "collect_findings"]
```

- [ ] **Step 10.5: Implement `pkm/lint/rules.py`**

This is the largest file in M4 — ~350 lines. Structure: snapshot loader, then one function per rule, then `collect_findings` runs them all.

```python
"""Lint rules — pure detection (no mutation).

13 rules: 6 errors + 7 warnings. Each returns Iterable[LintFinding]. The
CLI orchestrator (commands/lint.py) calls `collect_findings(root)`.

Spec reference: §6.5.
"""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pkm.errors import PKMValidationError
from pkm.store.frontmatter import parse
from pkm.store.frontmatter_schemas import (
    CAPTURE_LANGS,
    CAPTURE_REQUIRED,
    CAPTURE_SOURCE_TYPES,
    CAPTURE_STATUSES,
    CHUNK_LANGS,
    CHUNK_REQUIRED,
    CHUNK_STATUSES,
    WIKI_BUCKETS,
    WIKI_LANGS,
    WIKI_REQUIRED,
    WIKI_STATUSES,
    WRITING_LANGS,
    WRITING_PURPOSES,
    WRITING_REQUIRED,
    WRITING_STATUSES,
)
from pkm.store.wiki_paths import iter_all_wiki

_STALE_DRAFT_DAYS = 30
_STALE_STUB_DAYS = 30
_LARGE_CHUNK_DAYS = 60

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
_CITATION_RE = re.compile(r"\[[^\]]+\]\((data/[^)]+)\)")
_HANGUL_RE = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class LintFinding:
    code: str
    severity: str   # "error" | "warning"
    path: str       # repo-relative
    message: str
    field: str | None = None
    fixable: bool = False


@dataclass
class _Doc:
    """Pre-parsed snapshot row."""
    path: Path
    rel: str
    kind: str       # "capture" | "chunk" | "wiki" | "writing"
    fm: dict
    body: str
    mtime: float
    parse_error: str | None = None


@dataclass
class _Snapshot:
    docs: list[_Doc] = field(default_factory=list)

    def by_kind(self, kind: str) -> list[_Doc]:
        return [d for d in self.docs if d.kind == kind]


def _kind_for(rel: str) -> str | None:
    if rel.startswith("data/raw/captures/") and rel.endswith(".md"):
        return "capture"
    if rel.startswith("data/raw/chunks/") and rel.endswith("/README.md"):
        return "chunk"
    if rel.startswith("data/wiki/") and rel.endswith(".md"):
        return "wiki"
    if rel.startswith("data/writing/") and rel.endswith(".md"):
        return "writing"
    return None


def _load_snapshot(root: Path) -> _Snapshot:
    snap = _Snapshot()
    data = root / "data"
    if not data.exists():
        return snap
    for p in sorted(data.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        kind = _kind_for(rel)
        if kind is None:
            continue
        try:
            fm, body = parse(p.read_text(encoding="utf-8"))
            err = None
        except PKMValidationError as e:
            fm, body, err = {}, "", str(e)
        snap.docs.append(
            _Doc(path=p, rel=rel, kind=kind, fm=fm, body=body,
                 mtime=p.stat().st_mtime, parse_error=err)
        )
    return snap


# --------- Errors ---------

_REQUIRED_BY_KIND = {
    "capture": CAPTURE_REQUIRED,
    "chunk": CHUNK_REQUIRED,
    "wiki": WIKI_REQUIRED,
    "writing": WRITING_REQUIRED,
}

_ENUMS_BY_KIND = {
    "capture": [
        ("status", CAPTURE_STATUSES),
        ("source_type", CAPTURE_SOURCE_TYPES),
        ("lang", CAPTURE_LANGS),
    ],
    "chunk": [("status", CHUNK_STATUSES), ("lang", CHUNK_LANGS)],
    "wiki": [
        ("bucket", WIKI_BUCKETS),
        ("status", WIKI_STATUSES),
        ("lang", WIKI_LANGS),
    ],
    "writing": [
        ("purpose", WRITING_PURPOSES),
        ("status", WRITING_STATUSES),
        ("lang", WRITING_LANGS),
    ],
}


def _missing_field(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        if d.parse_error:
            yield LintFinding("MISSING_FIELD", "error", d.rel,
                              f"frontmatter unparsable: {d.parse_error}", fixable=False)
            continue
        for key in _REQUIRED_BY_KIND.get(d.kind, ()):
            if key not in d.fm:
                fixable = key in ("created_at", "slug")
                yield LintFinding("MISSING_FIELD", "error", d.rel,
                                  f"required field {key!r} missing",
                                  field=key, fixable=fixable)


def _invalid_value(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        for key, allowed in _ENUMS_BY_KIND.get(d.kind, []):
            val = d.fm.get(key)
            if val is not None and val not in allowed:
                yield LintFinding("INVALID_VALUE", "error", d.rel,
                                  f"{key}={val!r} not in {allowed}", field=key)


def _duplicate_slug(snap: _Snapshot) -> Iterator[LintFinding]:
    # Group: (kind, bucket-or-None) → slug → [paths]
    groups: dict[tuple[str, str | None], dict[str, list[str]]] = {}
    for d in snap.docs:
        slug = d.fm.get("slug") if d.kind != "chunk" else d.fm.get("topic")
        if not slug:
            continue
        bucket = d.fm.get("bucket") if d.kind == "wiki" else None
        key = (d.kind, bucket)
        groups.setdefault(key, {}).setdefault(slug, []).append(d.rel)
    for (_kind, _bucket), bucket_slugs in groups.items():
        for slug, paths in bucket_slugs.items():
            if len(paths) > 1:
                for p in paths:
                    yield LintFinding(
                        "DUPLICATE_SLUG", "error", p,
                        f"slug {slug!r} appears in {len(paths)} files: {', '.join(paths)}",
                    )


def _broken_wikilink(snap: _Snapshot) -> Iterator[LintFinding]:
    known = {d.fm.get("slug") for d in snap.docs if d.kind == "wiki" and d.fm.get("slug")}
    for d in snap.docs:
        if d.kind not in ("wiki", "writing"):
            continue
        for m in _WIKILINK_RE.findall(d.body):
            if m not in known:
                yield LintFinding(
                    "BROKEN_WIKILINK", "error", d.rel,
                    f"[[{m}]] doesn't resolve to any wiki slug",
                )


def _broken_derived_from(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.docs:
        derived = d.fm.get("derived_from")
        if not isinstance(derived, list):
            continue
        for ref in derived:
            if not isinstance(ref, str):
                continue
            if not (root / ref).exists():
                yield LintFinding(
                    "BROKEN_DERIVED_FROM", "error", d.rel,
                    f"derived_from path doesn't exist: {ref}",
                )


def _orphan_promoted_source(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    captures_by_rel = {d.rel: d for d in snap.docs if d.kind == "capture"}
    for d in snap.docs:
        if d.kind != "wiki":
            continue
        pf = d.fm.get("promoted_from")
        if not pf:
            continue
        src = captures_by_rel.get(pf)
        if src is None:
            continue  # BROKEN_DERIVED_FROM-style would catch missing files separately
        if src.fm.get("status") != "archived":
            yield LintFinding(
                "ORPHAN_PROMOTED_SOURCE", "error", d.rel,
                f"promoted_from {pf} has status={src.fm.get('status')!r}, expected 'archived'",
                fixable=True,
            )


# --------- Warnings ---------

_NOW = time.time  # indirection so tests can monkeypatch if needed


def _stale_draft(snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _STALE_DRAFT_DAYS * 86400
    for d in snap.by_kind("capture"):
        if d.fm.get("status") == "draft" and d.mtime < cutoff:
            yield LintFinding("STALE_DRAFT", "warning", d.rel,
                              f"draft for >{_STALE_DRAFT_DAYS} days; review or rm")


def _stale_stub(snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _STALE_STUB_DAYS * 86400
    for d in snap.by_kind("wiki"):
        if d.fm.get("status") == "stub" and d.mtime < cutoff:
            yield LintFinding("STALE_STUB", "warning", d.rel,
                              f"stub for >{_STALE_STUB_DAYS} days; expand or deprecate")


def _orphan_wiki(snap: _Snapshot) -> Iterator[LintFinding]:
    # Build incoming-link map
    incoming: dict[str, set[str]] = {}
    for d in snap.docs:
        if d.kind not in ("wiki", "writing", "capture"):
            continue
        for slug in _WIKILINK_RE.findall(d.body):
            incoming.setdefault(slug, set()).add(d.rel)
    derived_from_targets: set[str] = set()
    for d in snap.docs:
        for ref in (d.fm.get("derived_from") or []):
            if isinstance(ref, str):
                derived_from_targets.add(ref)
    for d in snap.by_kind("wiki"):
        slug = d.fm.get("slug")
        if not slug:
            continue
        has_incoming = bool(incoming.get(slug))
        is_derived_target = d.rel in derived_from_targets
        has_tags = bool(d.fm.get("tags"))
        if not (has_incoming or is_derived_target or has_tags):
            yield LintFinding("ORPHAN_WIKI", "warning", d.rel,
                              "no incoming wikilinks, derived_from, or tags")


def _large_chunk_never_promoted(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    cutoff = _NOW() - _LARGE_CHUNK_DAYS * 86400
    # Build set of paths referenced by any wiki page (via derived_from or wikilinks/citations)
    referenced: set[str] = set()
    for d in snap.docs:
        if d.kind != "wiki":
            continue
        for ref in (d.fm.get("derived_from") or []):
            if isinstance(ref, str):
                referenced.add(ref)
        for m in _CITATION_RE.findall(d.body):
            referenced.add(m)
    for d in snap.by_kind("chunk"):
        if d.fm.get("status") != "ready":
            continue
        if d.mtime >= cutoff:
            continue
        topic_dir = d.path.parent.relative_to(root).as_posix() + "/"
        if any(r.startswith(topic_dir) for r in referenced):
            continue
        yield LintFinding(
            "LARGE_CHUNK_NEVER_PROMOTED", "warning", d.rel,
            f"chunk ready for >{_LARGE_CHUNK_DAYS} days with no wiki references; consider synthesizing.",
        )


def _lang_inconsistent(snap: _Snapshot) -> Iterator[LintFinding]:
    # Heuristic: declared lang=ko but body has zero Hangul AND >100 chars → mismatch
    # Declared lang=en but body has Hangul → mismatch
    for d in snap.docs:
        body = d.body
        if len(body) < 80:
            continue
        lang = d.fm.get("lang")
        has_hangul = bool(_HANGUL_RE.search(body))
        if lang == "ko" and not has_hangul:
            yield LintFinding("LANG_INCONSISTENT", "warning", d.rel,
                              "declared lang=ko but body has no Hangul characters")
        elif lang == "en" and has_hangul:
            yield LintFinding("LANG_INCONSISTENT", "warning", d.rel,
                              "declared lang=en but body contains Hangul characters")


def _raw_body_mutated(snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.by_kind("capture"):
        if d.fm.get("status") != "reviewed":
            continue
        stored = d.fm.get("body_hash")
        if not stored:
            continue  # legacy / pre-M4 capture — skip silently
        actual = hashlib.sha256(d.body.encode("utf-8")).hexdigest()
        if actual != stored:
            yield LintFinding(
                "RAW_BODY_MUTATED", "warning", d.rel,
                "body changed after status=reviewed (immutability violation)",
            )


def _broken_citation(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    for d in snap.by_kind("wiki"):
        for ref in _CITATION_RE.findall(d.body):
            if not (root / ref).exists():
                yield LintFinding("BROKEN_CITATION", "warning", d.rel,
                                  f"citation path doesn't exist: {ref}")


# --------- Orchestrator ---------

def collect_findings(root: Path) -> list[LintFinding]:
    """Run every rule against the root and return findings sorted by (path, code)."""
    snap = _load_snapshot(root)
    out: list[LintFinding] = []
    out.extend(_missing_field(snap))
    out.extend(_invalid_value(snap))
    out.extend(_duplicate_slug(snap))
    out.extend(_broken_wikilink(snap))
    out.extend(_broken_derived_from(root, snap))
    out.extend(_orphan_promoted_source(root, snap))
    out.extend(_stale_draft(snap))
    out.extend(_stale_stub(snap))
    out.extend(_orphan_wiki(snap))
    out.extend(_large_chunk_never_promoted(root, snap))
    out.extend(_lang_inconsistent(snap))
    out.extend(_raw_body_mutated(snap))
    out.extend(_broken_citation(root, snap))
    out.sort(key=lambda f: (f.path, f.code))
    return out
```

- [ ] **Step 10.6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_lint_errors.py tests/test_lint_warnings.py -v
```

Expected: 13 passes.

If `test_raw_body_mutated` fails because the parser strips `body_hash` from frontmatter when it's a string with all-hex chars, sanity-check:
```bash
.venv/bin/python -c "from pkm.store.frontmatter import parse; print(parse(open('/tmp/x.md').read()))"
```
The hex string should round-trip as a plain string.

- [ ] **Step 10.7: Commit**

```bash
git add pkm/lint/ tests/test_lint_errors.py tests/test_lint_warnings.py
git commit -m "$(cat <<'EOF'
M4.10: pkm.lint.rules — 6 errors + 7 warnings, detection only

LintFinding dataclass + 13 rule functions + collect_findings orchestrator.
RAW_BODY_MUTATED is opt-in via body_hash frontmatter field (legacy
captures without the hash skip silently). All rules are pure functions
over a pre-loaded snapshot — they don't re-read disk per rule.
EOF
)"
```

---

### Task 11: `pkm/lint/fixers.py` — 2 auto-fixes (TDD)

**Files:**
- Create: `pkm/lint/fixers.py`, `tests/test_lint_fixers.py`

**Goal:** Two auto-fix functions corresponding to the 2 spec-marked items:

1. `fix_missing_field(root, finding) → bool` — handles `MISSING_FIELD` for `created_at` and `slug` only.
   - `created_at`: fill with the file's mtime in ISO 8601.
   - `slug`: derive from the file stem (preserves the date prefix on captures; plain stem on wiki/writing).

2. `fix_orphan_promoted_source(root, finding) → bool` — for the wiki finding, set the source capture's `status: archived`.

Each function returns `True` if it changed anything (and it goes through `post_mutation`), `False` otherwise. The caller in Task 12 walks the findings list and dispatches.

#### Steps

- [ ] **Step 11.1: Write failing tests `tests/test_lint_fixers.py`**

```python
"""Tests for lint auto-fixers."""
from __future__ import annotations
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.fixers import fix_missing_field, fix_orphan_promoted_source
from pkm.lint.rules import LintFinding

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def test_fix_missing_field_created_at(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: X\nslug: 2026-05-01-x\n"
                  "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
                 encoding="utf-8")
    finding = LintFinding("MISSING_FIELD", "error", "data/raw/captures/2026-05-01-x.md",
                          "missing", field="created_at", fixable=True)
    assert fix_missing_field(repo, finding) is True
    assert "created_at:" in p.read_text(encoding="utf-8")


def test_fix_missing_field_slug_from_file_stem(tmp_path: Path):
    """Slug fixer uses the file stem — preserves date prefix for captures."""
    repo = _init(tmp_path)
    # Capture's file stem already includes the date prefix
    p = repo / "data" / "raw" / "captures" / "2026-05-01-some-title.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Some Title\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
                 encoding="utf-8")
    finding = LintFinding("MISSING_FIELD", "error",
                          "data/raw/captures/2026-05-01-some-title.md",
                          "missing", field="slug", fixable=True)
    assert fix_missing_field(repo, finding) is True
    # Date-prefixed slug, derived from file stem
    assert "slug: 2026-05-01-some-title" in p.read_text(encoding="utf-8")


def test_fix_missing_field_slug_for_wiki_uses_stem(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "wiki" / "concepts" / "oauth.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: OAuth\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: stub\nlang: ko\ntags: []\n---\nbody\n",
                 encoding="utf-8")
    finding = LintFinding("MISSING_FIELD", "error",
                          "data/wiki/concepts/oauth.md",
                          "missing", field="slug", fixable=True)
    assert fix_missing_field(repo, finding) is True
    assert "slug: oauth" in p.read_text(encoding="utf-8")


def test_fix_missing_field_unfixable_returns_false(tmp_path: Path):
    repo = _init(tmp_path)
    finding = LintFinding("MISSING_FIELD", "error", "data/wiki/concepts/x.md",
                          "missing", field="title", fixable=False)
    assert fix_missing_field(repo, finding) is False


def test_fix_orphan_promoted_source(tmp_path: Path):
    repo = _init(tmp_path)
    src = repo / "data" / "raw" / "captures" / "2026-05-01-x.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\ntitle: X\nslug: 2026-05-01-x\n"
                    "created_at: 2026-05-01T10:00:00+09:00\n"
                    "status: reviewed\nsource_type: text\nlang: ko\n---\nbody\n",
                   encoding="utf-8")
    wiki = repo / "data" / "wiki" / "concepts" / "x.md"
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text("---\ntitle: X\nslug: x\nbucket: concepts\n"
                     "created_at: 2026-05-02T10:00:00+09:00\n"
                     "updated_at: 2026-05-02T10:00:00+09:00\n"
                     "status: stub\nlang: ko\ntags: []\n"
                     "promoted_from: data/raw/captures/2026-05-01-x.md\n---\nbody\n",
                    encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    finding = LintFinding("ORPHAN_PROMOTED_SOURCE", "error",
                          "data/wiki/concepts/x.md",
                          "...", fixable=True)
    assert fix_orphan_promoted_source(repo, finding) is True
    assert "status: archived" in src.read_text(encoding="utf-8")
```

- [ ] **Step 11.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_lint_fixers.py -v
```

Expected: 5 fails (no `fixers` module).

- [ ] **Step 11.3: Implement `pkm/lint/fixers.py`**

```python
"""Auto-fixers for the 2 spec-marked lint findings.

Spec §6.5 marks two items as fixable:
  - MISSING_FIELD (created_at, slug only)
  - ORPHAN_PROMOTED_SOURCE (set source status to archived)

Everything else is detect-only in V1. Each fixer returns True if it
changed anything, False otherwise. All file writes go through atomic_write
+ post_mutation so reindex + git commit happen.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pkm._mutations import post_mutation
from pkm.lint.rules import LintFinding
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.log import LogEvent


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def fix_missing_field(root: Path, finding: LintFinding) -> bool:
    """Fix MISSING_FIELD for `created_at` or `slug`. Returns True if mutated."""
    if finding.code != "MISSING_FIELD" or not finding.fixable:
        return False
    if finding.field not in ("created_at", "slug"):
        return False

    target = root / finding.path
    if not target.exists():
        return False
    fm, body = parse(target.read_text(encoding="utf-8"))

    if finding.field == "created_at":
        # Use file mtime as the inferred created_at
        ts = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC).astimezone()
        fm["created_at"] = ts.isoformat(timespec="seconds")
    else:  # slug
        # Derive from the file stem — captures use date-prefixed stems
        # (`2026-05-01-foo`) and that prefix is load-bearing M2 invariant.
        # Wiki/writing stems are plain kebab-case.
        fm["slug"] = target.stem

    atomic_write(target, serialize(fm, body))
    post_mutation(
        root,
        LogEvent(type="lint.fix",
                 ref=fm.get("slug") or target.stem,
                 message=f"missing_field {finding.field}"),
        paths=[finding.path],
    )
    return True


def fix_orphan_promoted_source(root: Path, finding: LintFinding) -> bool:
    """Set the promoted_from source's status to 'archived'. Returns True if mutated."""
    if finding.code != "ORPHAN_PROMOTED_SOURCE" or not finding.fixable:
        return False
    wiki_p = root / finding.path
    if not wiki_p.exists():
        return False
    fm_w, _body_w = parse(wiki_p.read_text(encoding="utf-8"))
    src_rel = fm_w.get("promoted_from")
    if not src_rel:
        return False
    src = root / src_rel
    if not src.exists():
        return False
    fm_s, body_s = parse(src.read_text(encoding="utf-8"))
    if fm_s.get("status") == "archived":
        return False  # already correct (race with manual fix)
    fm_s["status"] = "archived"
    atomic_write(src, serialize(fm_s, body_s))
    post_mutation(
        root,
        LogEvent(type="lint.fix",
                 ref=fm_s.get("slug") or src.stem,
                 message="orphan_promoted_source → archived"),
        paths=[src_rel],
    )
    return True
```

- [ ] **Step 11.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_lint_fixers.py -v
```

Expected: 5 passes.

- [ ] **Step 11.5: Commit**

```bash
git add pkm/lint/fixers.py tests/test_lint_fixers.py
git commit -m "$(cat <<'EOF'
M4.11: pkm.lint.fixers — 2 spec-marked auto-fixes

MISSING_FIELD created_at (file mtime) + slug (file stem — preserves
date prefix on captures). ORPHAN_PROMOTED_SOURCE → source status: archived.
Each fix goes through post_mutation so reindex + git commit happen.
EOF
)"
```

---

### Task 12: `pkm lint` CLI (TDD)

**Files:**
- Create: `pkm/commands/lint.py`, `tests/test_lint_command.py`
- Modify: `pkm/cli.py`

**Goal:** `pkm lint [--fix] [--json] [--errors-only]`. Default: human-readable output of all findings, exit 0 unless errors exist (then exit 1). With `--errors-only`, suppress warnings AND exit code is gated only on errors. With `--json`, emit a structured payload with `{ok, errors: [...], warnings: [...], fixed: int}`. With `--fix`, run fixers on every fixable finding before reporting; the report excludes the fixed ones.

The exit code contract:
- No errors found → exit 0
- Errors found, --errors-only → exit 1
- Errors found, default → exit 1 (warnings don't gate)
- `--fix` succeeds in clearing all errors → exit 0

#### Steps

- [ ] **Step 12.1: Write failing tests `tests/test_lint_command.py`**

```python
"""Tests for `pkm lint` CLI."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _seed_clean(repo: Path) -> None:
    runner.invoke(app, ["capture", "create", "--slug", "ok",
                        "--title", "OK", "--lang", "ko",
                        "--root", str(repo)],
                  input="한국어 본문 OK\n" * 10)


def test_lint_clean_repo_exits_zero(tmp_path: Path):
    repo = _init(tmp_path)
    _seed_clean(repo)
    result = runner.invoke(app, ["lint", "--json", "--root", str(repo)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_lint_with_error_exits_one(tmp_path: Path):
    repo = _init(tmp_path)
    bad = repo / "data" / "wiki" / "concepts" / "p.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntitle: P\nslug: p\nbucket: bogus\n"
                    "created_at: 2026-05-01T10:00:00+09:00\n"
                    "updated_at: 2026-05-01T10:00:00+09:00\n"
                    "status: active\nlang: ko\ntags: []\n---\nbody\n",
                   encoding="utf-8")
    result = runner.invoke(app, ["lint", "--json", "--root", str(repo)])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(e["code"] == "INVALID_VALUE" for e in payload["errors"])


def test_lint_errors_only_suppresses_warnings(tmp_path: Path):
    repo = _init(tmp_path)
    # An ORPHAN_WIKI (warning) but no errors
    p = repo / "data" / "wiki" / "concepts" / "lonely.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: L\nslug: lonely\nbucket: concepts\n"
                  "created_at: 2026-05-01T10:00:00+09:00\n"
                  "updated_at: 2026-05-01T10:00:00+09:00\n"
                  "status: active\nlang: ko\ntags: []\n---\nbody\n",
                 encoding="utf-8")
    result = runner.invoke(app, ["lint", "--errors-only", "--json", "--root", str(repo)])
    assert result.exit_code == 0  # only warnings, errors-only ignores them
    payload = json.loads(result.stdout)
    assert "warnings" not in payload or payload["warnings"] == []


def test_lint_fix_applies_fixers(tmp_path: Path):
    repo = _init(tmp_path)
    # Capture missing created_at — fixable
    p = repo / "data" / "raw" / "captures" / "2026-05-01-z.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Z\nslug: 2026-05-01-z\n"
                  "status: draft\nsource_type: text\nlang: ko\n---\nbody\n",
                 encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed missing"], cwd=repo, check=True)

    result = runner.invoke(app, ["lint", "--fix", "--json", "--root", str(repo)])
    payload = json.loads(result.stdout)
    assert payload["fixed"] >= 1
    assert "created_at:" in p.read_text(encoding="utf-8")


def test_lint_human_output_lists_findings(tmp_path: Path):
    repo = _init(tmp_path)
    bad = repo / "data" / "wiki" / "concepts" / "p.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntitle: P\nslug: p\nbucket: concepts\n"
                    "created_at: 2026-05-01T10:00:00+09:00\n"
                    "updated_at: 2026-05-01T10:00:00+09:00\n"
                    "status: weird\nlang: ko\ntags: []\n---\nbody\n",
                   encoding="utf-8")
    result = runner.invoke(app, ["lint", "--root", str(repo)])
    assert result.exit_code == 1
    assert "INVALID_VALUE" in result.stdout
    assert "data/wiki/concepts/p.md" in result.stdout
```

- [ ] **Step 12.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_lint_command.py -v
```

Expected: 5 fails.

- [ ] **Step 12.3: Implement `pkm/commands/lint.py`**

```python
"""`pkm lint [--fix] [--json] [--errors-only]`.

Read-only by default. With --fix, dispatches the 2 spec-marked auto-fixers.

Spec reference: §6.5.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.lint.fixers import fix_missing_field, fix_orphan_promoted_source
from pkm.lint.rules import LintFinding, collect_findings


def _apply_fixes(root: Path, findings: list[LintFinding]) -> tuple[int, list[LintFinding]]:
    """Run fixers on every fixable finding. Returns (count_fixed, remaining_findings).

    Re-runs collect_findings after fixing so the post-fix snapshot is reported.
    """
    fixed = 0
    for f in findings:
        if not f.fixable:
            continue
        if f.code == "MISSING_FIELD":
            if fix_missing_field(root, f):
                fixed += 1
        elif f.code == "ORPHAN_PROMOTED_SOURCE":
            if fix_orphan_promoted_source(root, f):
                fixed += 1
    if fixed:
        return fixed, collect_findings(root)
    return 0, findings


def _to_dict(f: LintFinding) -> dict:
    return {
        "code": f.code,
        "severity": f.severity,
        "path": f.path,
        "message": f.message,
        "field": f.field,
        "fixable": f.fixable,
    }


def _human(findings: list[LintFinding], errors_only: bool) -> str:
    lines: list[str] = []
    for f in findings:
        if errors_only and f.severity != "error":
            continue
        marker = "✗" if f.severity == "error" else "~"
        field = f" [{f.field}]" if f.field else ""
        lines.append(f"  {marker} {f.severity:<7} {f.code:<28} {f.path}{field}: {f.message}")
    if not lines:
        return "No findings.\n"
    return "\n".join(lines) + "\n"


def register(app: typer.Typer) -> None:
    @app.command("lint")
    def lint_cmd(
        fix: bool = typer.Option(False, "--fix", help="Apply auto-fixes for fixable findings."),
        errors_only: bool = typer.Option(False, "--errors-only", help="Hide warnings; gate exit on errors only."),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Lint frontmatter, wikilinks, and provenance across the repo."""
        findings = collect_findings(root)
        fixed_count = 0
        if fix:
            fixed_count, findings = _apply_fixes(root, findings)

        errors = [f for f in findings if f.severity == "error"]
        warnings_ = [f for f in findings if f.severity == "warning"]
        any_errors = bool(errors)

        if json_out:
            payload: dict = {
                "ok": not any_errors,
                "errors": [_to_dict(f) for f in errors],
                "fixed": fixed_count,
            }
            if not errors_only:
                payload["warnings"] = [_to_dict(f) for f in warnings_]
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(_human(findings, errors_only=errors_only))
            if fixed_count:
                typer.echo(f"(auto-fixed {fixed_count} finding(s))")

        if any_errors:
            raise typer.Exit(code=1)
```

- [ ] **Step 12.4: Register in `pkm/cli.py`**

- [ ] **Step 12.5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_lint_command.py -v
```

Expected: 5 passes.

- [ ] **Step 12.6: Commit**

```bash
git add pkm/commands/lint.py pkm/cli.py tests/test_lint_command.py
git commit -m "$(cat <<'EOF'
M4.12: pkm lint [--fix] [--json] [--errors-only]

Read-only by default; --fix dispatches the 2 spec-marked auto-fixers
and re-runs collect_findings to report the post-fix snapshot.
--errors-only suppresses warnings AND restricts the exit-code gate.
JSON shape: {ok, errors[], warnings[]?, fixed}.
EOF
)"
```

---

### Task 13: Slash command templates `/promote` + `/lint` (TDD)

**Files:**
- Create: `pkm/templates/.claude/commands/promote.md`, `pkm/templates/.claude/commands/lint.md`
- Modify: `pkm/commands/init.py` (add 2 entries to `_FILES_FROM_TEMPLATES`)
- Create: `tests/test_init_m4_seeds.py`
- Modify: `pkm/templates/SCHEMA.md.template` (mention promote + wiki edit + lint workflows)

**Goal:** Two new slash command templates seeded by `pkm init`. Existing M2 init test (`tests/test_init.py`) covers the 3 M2 templates; we add a focused M4 test for the new ones plus the SCHEMA workflow update.

#### Steps

- [ ] **Step 13.1: Write failing tests `tests/test_init_m4_seeds.py`**

```python
"""Tests for the M4-seeded slash templates."""
from __future__ import annotations
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_init_seeds_promote_template(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / ".claude" / "commands" / "promote.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "/promote" in text
    assert "pkm promote" in text


def test_init_seeds_lint_template(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / ".claude" / "commands" / "lint.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "/lint" in text
    assert "pkm lint" in text
```

- [ ] **Step 13.2: Run failing tests**

```bash
.venv/bin/pytest tests/test_init_m4_seeds.py -v
```

Expected: 2 fails (files don't exist).

- [ ] **Step 13.3: Create `pkm/templates/.claude/commands/promote.md`**

```markdown
# /promote

Promote a reviewed capture into a wiki bucket.

1. Confirm the capture is `status: reviewed`. If not: `pkm capture set-status <ref> reviewed`.
2. Pick a bucket: `concepts | entities | notes | reports`.
3. (Optional) Pick a target slug: by default the date prefix is stripped from the capture slug.
4. Run: `pkm promote <ref> --to <bucket> [--slug NEW_SLUG] [--keep-source] --json`.
5. The wiki page lands at `data/wiki/<bucket>/<slug>.md` with `status: stub` and `promoted_from: <source>`.

Workflow detail: SCHEMA.md § Workflows → "Promote".
```

- [ ] **Step 13.4: Create `pkm/templates/.claude/commands/lint.md`**

```markdown
# /lint

Run the deterministic lint and (optionally) auto-fix the spec-marked items.

1. `pkm lint --json` — see all findings.
2. `pkm lint --errors-only --json` — for a CI-style hard-gate (exits 1 on errors only).
3. `pkm lint --fix --json` — auto-fix `MISSING_FIELD` (created_at, slug) and `ORPHAN_PROMOTED_SOURCE`. Other findings need human attention.

Lint codes (spec §6.5):
- Errors: MISSING_FIELD, INVALID_VALUE, DUPLICATE_SLUG, BROKEN_WIKILINK, BROKEN_DERIVED_FROM, ORPHAN_PROMOTED_SOURCE
- Warnings: STALE_DRAFT, STALE_STUB, ORPHAN_WIKI, LARGE_CHUNK_NEVER_PROMOTED, LANG_INCONSISTENT, RAW_BODY_MUTATED, BROKEN_CITATION

Workflow detail: SCHEMA.md § Workflows → "Lint".
```

- [ ] **Step 13.5: Modify `pkm/commands/init.py` to include the new templates**

Append to `_FILES_FROM_TEMPLATES` (in the same list-of-tuples style):

```python
    (".claude/commands/promote.md", ".claude/commands/promote.md"),
    (".claude/commands/lint.md", ".claude/commands/lint.md"),
```

- [ ] **Step 13.6: Update `pkm/templates/SCHEMA.md.template`**

In § 4 Workflows, add three new entries (after "Chunk curation"):

```markdown
### Promote
- Input: a reviewed capture.
- `pkm promote <ref> --to concepts|entities|notes|reports [--slug NEW] [--keep-source]`.
- Result: a stub wiki page at `data/wiki/<bucket>/<slug>.md` with `promoted_from: <source>`. Source flips to `archived` (unless `--keep-source`).

### Wiki edit (escape valve)
- `data/wiki/**` is deny-write under strict mode (`.claude/settings.json`). The only authorized mutation path is `pkm wiki edit`.
- `pkm wiki edit <wiki-ref> --replace < new_full_file.md` — replace whole file.
- `pkm wiki edit <wiki-ref> --patch < unified.diff` — apply a unified diff via `git apply`.
- Both modes validate frontmatter + wikilinks before writing.

### Lint
- `pkm lint --json` for the full report.
- `pkm lint --fix` to apply the 2 spec-marked auto-fixes.
```

Also update § 3 to describe the wiki + writing schemas (the existing template has a placeholder noting M4–M5).

- [ ] **Step 13.7: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_init_m4_seeds.py tests/test_init.py -v
```

Expected: all pass. The existing `test_init.py` may already check the count of seeded templates — if it asserts "exactly 3 templates", update that assertion to "exactly 5". (Read `tests/test_init.py` first; only edit if there's a hard-coded count.)

- [ ] **Step 13.8: Commit**

```bash
git add pkm/templates/.claude/commands/promote.md pkm/templates/.claude/commands/lint.md pkm/commands/init.py pkm/templates/SCHEMA.md.template tests/test_init_m4_seeds.py tests/test_init.py
git commit -m "$(cat <<'EOF'
M4.13: pkm init seeds /promote + /lint templates

Two new slash templates land under .claude/commands/. SCHEMA.md.template
gains Promote / Wiki Edit / Lint workflow entries. After init, the
project has 5 seeded slash commands (collect, research, review-captures,
promote, lint).
EOF
)"
```

---

### Task 14: README + lint clean + tag

**Files:**
- Modify: `README.md`
- Verify: full test suite + `ruff check` + `pyright` (if configured to gate)

**Goal:** Mark M4 done in the README, ensure the suite + lint pass, tag `m4-promote-lint-extract`.

#### Steps

- [ ] **Step 14.1: Run the full fast suite**

```bash
PKM_TEST_STUB_EMBEDDER=1 .venv/bin/pytest -q
```

Expected: ~250 passes, 0 failures. If anything fails, fix it (or surface to the human if it's truly outside M4 scope).

- [ ] **Step 14.2: Run lint**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/ruff format --check pkm tests
```

Fix any lint findings (most likely: unused imports, formatting drift).

- [ ] **Step 14.3: Run type check**

```bash
.venv/bin/pyright pkm
```

Fix any type errors. Heavy deps (`pdfplumber`, `markdownify`) may need `# type: ignore[import-untyped]` on the lazy import line if they don't ship stubs.

- [ ] **Step 14.4: Update `README.md`**

Add a row to the milestone table marking M4 done; under the "What's done" / commands section, add:
- `pkm extract <file> [--out PATH]` — PDF/HTML → md
- `pkm promote <ref> --to <bucket> [--slug NEW] [--keep-source]`
- `pkm demote <wiki-ref>`
- `pkm wiki edit <ref> {--replace|--patch}`
- `pkm lint [--fix] [--json] [--errors-only]`

Mention deps: `pip install hwi-pkm[extract]` for `pdfplumber` + `markdownify`.

- [ ] **Step 14.5: Smoke test the user happy path**

```bash
cd /tmp && rm -rf m4-smoke && mkdir m4-smoke && cd m4-smoke
.venv/bin/pkm init -f
echo "OAuth body" | .venv/bin/pkm capture create --slug oauth --title "OAuth" --json
.venv/bin/pkm capture set-status oauth reviewed
.venv/bin/pkm promote oauth --to concepts --json
.venv/bin/pkm lint --json
.venv/bin/pkm demote concepts/oauth --json
git log --oneline | head
```

Expected: everything succeeds, JSON outputs include `git_commit` SHAs, `git log` shows individual commits per mutation.

- [ ] **Step 14.6: Commit + tag**

```bash
git add README.md
git commit -m "M4.14: README + lint clean — M4 done"
git tag -a m4-promote-lint-extract -m "$(cat <<'EOF'
M4 — Promote, Lint & Extract

- pkm extract <file> [--out PATH] — PDF/HTML → markdown ([extract] extras)
- pkm wiki edit <ref> --replace|--patch — strict-mode escape valve
- pkm promote <ref> --to <bucket> [--slug NEW] [--keep-source]
- pkm demote <wiki-ref>
- pkm lint [--fix] [--json] [--errors-only]
  - 6 errors + 7 warnings detected
  - --fix handles MISSING_FIELD (created_at/slug) + ORPHAN_PROMOTED_SOURCE
- wiki + writing frontmatter schemas (writing's `pkm write new` lands in M5)
- pkm init seeds /promote + /lint slash templates (5 total now)

Out of scope: writing-origin promote/demote (M5), pkm write new (M5),
docx extract (V2), --deep LLM lint (V2).
EOF
)"
```

- [ ] **Step 14.7: Verify the tag**

```bash
git tag -l -n10 m4-promote-lint-extract
git log --oneline | head -20
```

Tag should annotate HEAD with the multi-line message.

---

## Definition of Done

- [ ] All 14 tasks committed with `M4.<n>:` prefix
- [ ] Tag `m4-promote-lint-extract` annotates the final M4.14 commit
- [ ] Full fast suite passes (~250 tests, no `slow` marker)
- [ ] `ruff check pkm tests` is clean
- [ ] `pyright pkm` is clean
- [ ] README mentions M4 done + the 5 new commands + `[extract]` extras
- [ ] `pkm init` on a fresh dir produces 5 slash templates
- [ ] Smoke test (Step 14.5) succeeds end-to-end and `git log` shows individual commits per mutation

## Notes for the executor

- **post_mutation always carries both source and destination paths for renames.** Promote stages source (status flip) AND wiki dest. Demote stages source (status flip) AND wiki dest (deletion). The git layer (M3.5.4) stages with `git add -A` so deletions are picked up automatically.
- **wikilink check is global.** When `pkm wiki edit` validates wikilinks, it consults every wiki page across all buckets — there's no per-bucket scoping. Same in lint's BROKEN_WIKILINK rule.
- **lint snapshot is loaded once per `pkm lint` invocation.** All 13 rules consume the same in-memory snapshot. If a rule needs git-history info (it doesn't currently), add it to the snapshot, not via shelling out from each rule.
- **Heavy deps stay lazy.** `pdfplumber` and `markdownify` are imported inside the function bodies, never at module top. `pkm --help` and `pytest --collect-only` should remain sub-second.
- **The 2 fixers each commit their own row to data/log.md.** Running `pkm lint --fix` on a repo with N fixable findings produces N log rows + N git commits. The CLI itself does not batch these — keeping commits 1:1 with mutations preserves the M3.5 invariant.
- **Carve-out error codes are stable.** `PROMOTE_FROM_WRITING_NOT_YET` and `DEMOTE_TO_WRITING_NOT_YET` will be expected by M5 tests. Don't rename them.
- **Plan-deviation policy** (per project memory): if a step turns out wrong, prefer a `fix:` commit on top of the M4.<n> commit with rationale rather than rewriting history. Tag stays where it lands at the end of M4.13.
