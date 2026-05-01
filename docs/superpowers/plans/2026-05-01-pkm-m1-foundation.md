# M1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project skeleton — Python package, CLI entry, frontmatter/files store primitives, `pkm init` and `pkm doctor` commands, test scaffolding (memory caps, stub embedder), CI baseline.

**Architecture:** Python 3.11+ package `pkm/` exposing the `pkm` console script via Typer. Pure-Python store primitives. Tests use pytest with conftest enforcing `RLIMIT_AS` cap and stub-embedder env default. CI runs ruff + pyright + fast pytest.

**Tech Stack:** Python 3.11+ · uv · Typer · PyYAML · pytest + pytest-timeout + pytest-forked · ruff · pyright · psutil. (Heavy deps like `sentence-transformers` and `sqlite-vec` are pinned in `pyproject.toml` but not used in M1.)

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` (esp. §2 Layout, §3 CLI, §8 Tests).

**Out-of-scope for M1 (deferred to later milestones):**
- M2: capture/chunks commands, log/index auto-update
- M3: SQLite + sqlite-vec, FTS5, embedder, search pipeline
- M4: promote, lint
- M5: write, AI bridge
- M6: dashboard
- M7: hardening

After M1 a developer can run `pkm init` in an empty directory and get a valid PKM scaffold, run `pkm doctor` and see a status report, run the test suite, and pass CI. No data manipulation features yet.

---

## File Structure

### Created in M1

```
pyproject.toml                        # deps, build config, scripts
.python-version                       # "3.11"
.gitignore                            # python + PKM-specific entries
README.md                             # minimal stub

.github/workflows/ci.yml              # ruff + pyright + pytest fast lane

pkm/__init__.py                       # version, __all__
pkm/cli.py                            # typer app, command registration
pkm/errors.py                         # PKMError hierarchy
pkm/store/__init__.py
pkm/store/frontmatter.py              # parse / serialize YAML frontmatter
pkm/store/files.py                    # slugify, atomic_write
pkm/commands/__init__.py
pkm/commands/init.py                  # `pkm init`
pkm/commands/doctor.py                # `pkm doctor` (basic checks)

pkm/templates/SCHEMA.md.template      # AI manual seed
pkm/templates/config.toml.template    # .pkm/config.toml seed
pkm/templates/settings.json.template  # .claude/settings.json seed
pkm/templates/gitignore.template      # repo .gitignore seed (post-init)

tests/__init__.py
tests/conftest.py                     # RSS cap, stub embedder env, markers
tests/test_frontmatter.py
tests/test_files.py
tests/test_init.py
tests/test_doctor.py
tests/fixtures/__init__.py
```

### Why these boundaries

- `pkm/store/` holds all file/IO primitives; future milestones add `index.py` here for SQLite.
- `pkm/commands/` holds one module per `pkm <subcommand>`. Each is small and testable.
- `pkm/templates/` holds static text seeds, separated from logic so `pkm init` is a tiny copy operation.
- `pkm/errors.py` is shared by all modules. Carries `code`/`message`/`hint` for JSON output (spec §3.1).
- `tests/conftest.py` enforces memory safety **before any test runs** (spec §8.3).

---

## Task list (executor checklist)

There are 11 tasks. Each is 5–15 minutes of focused work. Tasks 3, 4, 7, 8 use TDD. Others are scaffolding.

> **For each task, work in the order listed and run the exact commands shown.** Commit after every task. Use the commit messages provided.

---

### Task 1: Repo bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `README.md`

#### Steps

- [ ] **Step 1.1: Initialize git and uv**

```bash
cd /Users/ad03159868/Downloads/Claude_lab/hwi_PKM
git init -b main
```

- [ ] **Step 1.2: Write `.python-version`**

Content (single line, no newline issues):
```
3.11
```

- [ ] **Step 1.3: Write `pyproject.toml`**

```toml
[project]
name = "hwi-pkm"
version = "0.1.0-dev"
description = "Personal Knowledge Management system — solo PKM with Claude Code as primary AI agent."
requires-python = ">=3.11"
authors = [{ name = "hwijung-park" }]
readme = "README.md"
license = { text = "MIT" }

dependencies = [
    "typer>=0.12",
    "pyyaml>=6",
    "python-frontmatter>=1.1",  # used in later milestones; harmless now
    "psutil>=5.9",
]

[project.optional-dependencies]
# Heavy deps — pinned now so future milestones can `uv sync` consistently
ml = [
    "sentence-transformers>=2.7",
    "sqlite-vec>=0.1",
]
dev = [
    "pytest>=8",
    "pytest-timeout>=2.3",
    "pytest-forked>=1.6",
    "pytest-xdist>=3.6",
    "ruff>=0.5",
    "pyright>=1.1",
]

[project.scripts]
pkm = "pkm.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["pkm"]

[tool.pytest.ini_options]
markers = [
    "slow: requires real models, run sequentially",
]
addopts = "--timeout=300 --maxfail=5"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]
ignore = ["E501"]  # line length handled by formatter

[tool.pyright]
pythonVersion = "3.11"
include = ["pkm", "tests"]
typeCheckingMode = "basic"
```

- [ ] **Step 1.4: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.venv/
.env
dist/
build/

# IDEs
.idea/
.vscode/
*.swp
.DS_Store

# PKM build artifacts (per spec §2)
/dashboard/
/.pkm/index.db
/.pkm/cache/
/.pkm/config.local.toml
/.claude/settings.local.json

# Test artifacts
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 1.5: Write `README.md`**

```markdown
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
- [ ] M2 — Capture & Chunks
- [ ] M3 — Indexing & Search
- [ ] M4 — Promote & Lint
- [ ] M5 — AI bridge & Writing
- [ ] M6 — Dashboard
- [ ] M7 — Hardening

(See spec §9.3 for milestone definitions.)
```

- [ ] **Step 1.6: Verify dependency resolution**

```bash
uv sync --all-extras
```
Expected: dependencies install, `.venv/` created, exit 0. If `uv` not installed, install it first (`brew install uv` or `pipx install uv`).

- [ ] **Step 1.7: Commit**

```bash
git add pyproject.toml .python-version .gitignore README.md
git commit -m "M1.1: repo bootstrap (pyproject, gitignore, readme)"
```

---

### Task 2: Errors module

**Files:**
- Create: `pkm/__init__.py`
- Create: `pkm/errors.py`

This module is pure boilerplate — TDD adds little. We add a basic test for the `to_dict` JSON contract because that contract is consumed by the CLI later.

#### Steps

- [ ] **Step 2.1: Write `pkm/__init__.py`**

```python
"""hwi_PKM — solo personal knowledge management.

Markdown files are the source of truth. Claude Code orchestrates a
deterministic CLI to capture, curate, promote, and search knowledge.
"""
__version__ = "0.1.0-dev"
__all__ = ["__version__"]
```

- [ ] **Step 2.2: Write `pkm/errors.py`**

```python
"""PKM exception hierarchy.

All user-facing errors derive from PKMError. Each carries a stable `code`
suitable for JSON output and a `hint` field for actionable user guidance.

Spec reference: §3.1 (error JSON shape), §5.7 (failure mode codes).
"""
from __future__ import annotations


class PKMError(Exception):
    """Base for all PKM errors."""

    code: str = "PKM_ERROR"

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


class PKMConfigError(PKMError):
    """Configuration is invalid or contradictory."""
    code = "CONFIG_ERROR"


class PKMValidationError(PKMError):
    """User input or persisted data fails validation."""
    code = "VALIDATION_ERROR"


class PKMStateError(PKMError):
    """System is in an unexpected state (file missing, invalid status, etc.)."""
    code = "STATE_ERROR"


class PKMNotFoundError(PKMError):
    """Requested resource (file, slug, topic) does not exist."""
    code = "NOT_FOUND"
```

- [ ] **Step 2.3: Quick smoke test (optional, no test file yet — sanity check via REPL)**

```bash
.venv/bin/python -c "from pkm.errors import PKMError; e = PKMError('x', 'y'); print(e.to_dict())"
```
Expected: `{'code': 'PKM_ERROR', 'message': 'x', 'hint': 'y'}`

- [ ] **Step 2.4: Commit**

```bash
git add pkm/__init__.py pkm/errors.py
git commit -m "M1.2: package skeleton + PKMError hierarchy"
```

---

### Task 3: Frontmatter parser (TDD)

**Files:**
- Create: `pkm/store/__init__.py`
- Create: `pkm/store/frontmatter.py`
- Test: `tests/__init__.py`
- Test: `tests/test_frontmatter.py`

#### Steps

- [ ] **Step 3.1: Create empty test/store init files**

```bash
touch pkm/store/__init__.py tests/__init__.py
```

- [ ] **Step 3.2: Write the failing tests `tests/test_frontmatter.py`**

```python
"""Tests for pkm.store.frontmatter."""
from __future__ import annotations
import pytest
from pkm.store.frontmatter import parse, serialize
from pkm.errors import PKMValidationError


def test_parse_with_frontmatter():
    text = "---\ntitle: foo\nlang: ko\n---\nbody"
    fm, body = parse(text)
    assert fm == {"title": "foo", "lang": "ko"}
    assert body == "body"


def test_parse_without_frontmatter():
    text = "no frontmatter here"
    fm, body = parse(text)
    assert fm == {}
    assert body == "no frontmatter here"


def test_parse_unclosed_frontmatter_raises():
    with pytest.raises(PKMValidationError, match="not closed"):
        parse("---\ntitle: foo\nbody without close")


def test_parse_invalid_yaml_raises():
    with pytest.raises(PKMValidationError, match="Invalid YAML"):
        parse("---\nkey: : :\n---\nbody")


def test_parse_non_mapping_frontmatter_raises():
    with pytest.raises(PKMValidationError, match="mapping"):
        parse("---\n- item1\n- item2\n---\nbody")


def test_serialize_roundtrip_korean():
    fm = {"title": "한글 제목", "tags": ["인증", "보안"]}
    body = "본문 텍스트입니다."
    text = serialize(fm, body)
    fm2, body2 = parse(text)
    assert fm2 == fm
    assert body2 == body


def test_serialize_empty_frontmatter():
    assert serialize({}, "body") == "body"


def test_serialize_preserves_key_order():
    fm = {"z": 1, "a": 2, "m": 3}
    text = serialize(fm, "")
    # Keys appear in insertion order (sort_keys=False)
    z_idx = text.index("z:")
    a_idx = text.index("a:")
    m_idx = text.index("m:")
    assert z_idx < a_idx < m_idx
```

- [ ] **Step 3.3: Run tests — they should fail (no module yet)**

```bash
.venv/bin/pytest tests/test_frontmatter.py -v
```
Expected: ImportError / ModuleNotFoundError on `pkm.store.frontmatter`.

- [ ] **Step 3.4: Write `pkm/store/frontmatter.py`**

```python
"""Markdown + YAML frontmatter parser/serializer.

Format::

    ---
    key: value
    ---
    body text

The `---` delimiter must appear at the very start of the file. If absent,
parse() returns an empty dict and the full text as body.

Spec reference: §6.1 (frontmatter schemas).
"""
from __future__ import annotations

import yaml

from pkm.errors import PKMValidationError

_DELIM = "---\n"


def parse(text: str) -> tuple[dict, str]:
    """Parse markdown text into (frontmatter_dict, body_text).

    Returns ({}, text) if no frontmatter is present.

    Raises PKMValidationError if frontmatter is malformed (unclosed, invalid
    YAML, or not a mapping at top level).
    """
    if not text.startswith(_DELIM):
        return {}, text
    try:
        end = text.index(_DELIM, len(_DELIM))
    except ValueError:
        raise PKMValidationError(
            "Frontmatter not closed",
            hint="Add a '---' line to close the frontmatter block.",
        ) from None
    fm_text = text[len(_DELIM):end]
    body = text[end + len(_DELIM):]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise PKMValidationError(f"Invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise PKMValidationError("Frontmatter must be a YAML mapping (key: value)")
    return fm, body


def serialize(meta: dict, body: str) -> str:
    """Serialize (frontmatter, body) back to markdown text.

    Empty meta produces a body-only string with no delimiters.
    """
    if not meta:
        return body
    fm_text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip("\n")
    return f"{_DELIM}{fm_text}\n{_DELIM}{body}"
```

- [ ] **Step 3.5: Run tests — should pass**

```bash
.venv/bin/pytest tests/test_frontmatter.py -v
```
Expected: 8 passed.

- [ ] **Step 3.6: Commit**

```bash
git add pkm/store/__init__.py pkm/store/frontmatter.py tests/__init__.py tests/test_frontmatter.py
git commit -m "M1.3: frontmatter parser/serializer with TDD"
```

---

### Task 4: Files store — slugify & atomic write (TDD)

**Files:**
- Create: `pkm/store/files.py`
- Test: `tests/test_files.py`

#### Steps

- [ ] **Step 4.1: Write the failing tests `tests/test_files.py`**

```python
"""Tests for pkm.store.files."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path

import pytest

from pkm.store.files import atomic_write, date_prefix_slug, slugify


def test_slugify_simple():
    assert slugify("Hello World") == "hello-world"


def test_slugify_korean_preserved():
    assert slugify("한글 제목 테스트") == "한글-제목-테스트"


def test_slugify_korean_stripped_when_disabled():
    s = slugify("한글 Hello World", allow_korean=False)
    assert "한" not in s
    assert "hello-world" in s


def test_slugify_punctuation_removed():
    assert slugify("Why? Auth/OAuth!") == "why-auth-oauth"


def test_slugify_collapses_multiple_hyphens():
    assert slugify("a--b---c") == "a-b-c"


def test_slugify_strips_edge_hyphens():
    assert slugify("---a-b---") == "a-b"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("???")


def test_slugify_lowercases():
    assert slugify("OAuth") == "oauth"


def test_date_prefix_slug():
    assert date_prefix_slug("Hello", on=date(2026, 5, 1)) == "2026-05-01-hello"


def test_date_prefix_slug_korean():
    assert date_prefix_slug("한글 제목", on=date(2026, 5, 1)) == "2026-05-01-한글-제목"


def test_atomic_write_creates_parent_dir(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    atomic_write(target, "content")
    assert target.read_text(encoding="utf-8") == "content"


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "file.txt"
    atomic_write(target, "first")
    atomic_write(target, "second")
    assert target.read_text(encoding="utf-8") == "second"


def test_atomic_write_no_partial_file_on_failure(tmp_path: Path, monkeypatch):
    """If os.replace fails mid-way, no .tmp file remains and target is untouched."""
    target = tmp_path / "file.txt"

    def boom(*a, **k):
        raise OSError("simulated failure")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated"):
        atomic_write(target, "content")

    assert not target.exists()
    leftovers = list(tmp_path.glob(".file.txt.*.tmp"))
    assert not leftovers


def test_atomic_write_korean_content(tmp_path: Path):
    target = tmp_path / "ko.md"
    atomic_write(target, "한글 본문 내용\n")
    assert target.read_text(encoding="utf-8") == "한글 본문 내용\n"
```

- [ ] **Step 4.2: Run tests — should fail**

```bash
.venv/bin/pytest tests/test_files.py -v
```
Expected: ModuleNotFoundError on `pkm.store.files`.

- [ ] **Step 4.3: Write `pkm/store/files.py`**

```python
"""File store primitives: slugify, date-prefixed slugs, atomic write.

V1 keeps slug rules simple:
  - lowercase
  - spaces → hyphens
  - punctuation collapses to single hyphens
  - Korean characters preserved by default (allow_korean=True)
  - non-Korean non-ASCII stripped
  - V2 may add proper romanization

Atomic write uses tempfile + os.replace, which is atomic on POSIX.

Spec reference: §3.2 (slug semantics), §8.6 (atomicity).
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import date
from pathlib import Path

# Allow word chars, hyphens, and Korean. Strip everything else to hyphens.
_NON_SLUG_KEEP_KO = re.compile(r"[^\w\-가-힣ㄱ-ㅎㅏ-ㅣ]+", re.UNICODE)
_NON_SLUG_ASCII = re.compile(r"[^a-z0-9\-]+")
_MULTI_HYPHEN = re.compile(r"-+")


def slugify(title: str, *, allow_korean: bool = True) -> str:
    """Convert a title into a kebab-case slug.

    Args:
        title: arbitrary string
        allow_korean: if True, preserve Korean syllables/jamo; otherwise
                      strip non-ASCII entirely

    Returns:
        kebab-case slug

    Raises:
        ValueError: if input produces an empty slug
    """
    s = title.strip().lower()
    s = s.replace(" ", "-")
    if allow_korean:
        s = _NON_SLUG_KEEP_KO.sub("-", s)
    else:
        s = _NON_SLUG_ASCII.sub("-", s)
    s = _MULTI_HYPHEN.sub("-", s).strip("-")
    if not s:
        raise ValueError(f"Title produces empty slug: {title!r}")
    return s


def date_prefix_slug(
    title: str,
    *,
    on: date | None = None,
    allow_korean: bool = True,
) -> str:
    """Generate a YYYY-MM-DD-<slug> identifier."""
    on = on or date.today()
    return f"{on.isoformat()}-{slugify(title, allow_korean=allow_korean)}"


def atomic_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text to `path` atomically.

    Strategy: write to a sibling tempfile, fsync, then os.replace into place.
    On POSIX `os.replace` is atomic. Parent directory is created if missing.

    Cleans up the tempfile on any failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
```

- [ ] **Step 4.4: Run tests — should pass**

```bash
.venv/bin/pytest tests/test_files.py -v
```
Expected: 14 passed.

- [ ] **Step 4.5: Commit**

```bash
git add pkm/store/files.py tests/test_files.py
git commit -m "M1.4: files store — slugify + atomic_write with TDD"
```

---

### Task 5: CLI entry point

**Files:**
- Create: `pkm/cli.py`
- Create: `pkm/commands/__init__.py`

#### Steps

- [ ] **Step 5.1: Write `pkm/commands/__init__.py`**

```python
"""Subcommand modules. Each module exposes a Typer command via `register(app)`."""
```

- [ ] **Step 5.2: Write `pkm/cli.py`**

```python
"""`pkm` console entry point.

This module wires up Typer and registers each subcommand. Subcommands live
in `pkm/commands/<name>.py` and expose a `register(app)` function.

Run `pkm --help` to see the full command tree.

Spec reference: §3.2 (command surface).
"""
from __future__ import annotations

import sys

import typer

from pkm import __version__
from pkm.errors import PKMError

app = typer.Typer(
    name="pkm",
    help="hwi_PKM — solo personal knowledge management.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pkm {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Top-level callback (handles --version)."""


def _register_all() -> None:
    # Imported here to avoid circular imports during module-init.
    from pkm.commands import init as init_cmd
    from pkm.commands import doctor as doctor_cmd

    init_cmd.register(app)
    doctor_cmd.register(app)


_register_all()


def main() -> None:
    """Entry point used by `[project.scripts] pkm = "pkm.cli:main"` if needed."""
    try:
        app()
    except PKMError as e:
        typer.echo(f"Error [{e.code}]: {e.message}", err=True)
        if e.hint:
            typer.echo(f"  hint: {e.hint}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

> Note: `pyproject.toml` declares `pkm = "pkm.cli:app"`. Typer's `app` is itself callable, so this works. We define `main()` as a safer wrapper for unhandled `PKMError`s. If you prefer the wrapper, change pyproject to `pkm = "pkm.cli:main"`. **Keep `:app` for now** — Task 8 verifies error handling explicitly.

- [ ] **Step 5.3: Verify CLI works**

```bash
.venv/bin/pkm --version
```
Expected: `pkm 0.1.0-dev` (Note: this will fail until commands are registered. Stub `init` and `doctor` modules are added in Tasks 7 and 8 — this verification is deferred to Step 7.6 / 8.5.)

For now verify imports succeed:
```bash
.venv/bin/python -c "from pkm.cli import app; print(type(app).__name__)"
```
Expected: `Typer` (will fail with ImportError on `pkm.commands.init` / `doctor` — that's OK for now). To make this pass we add empty stubs:

- [ ] **Step 5.4: Add empty command stubs to keep import working**

`pkm/commands/init.py`:
```python
"""`pkm init` — placeholder. Real impl in Task 7."""
import typer

def register(app: typer.Typer) -> None:
    @app.command("init")
    def _stub() -> None:
        """(stub — implemented in M1 Task 7)"""
        raise NotImplementedError("init not implemented yet")
```

`pkm/commands/doctor.py`:
```python
"""`pkm doctor` — placeholder. Real impl in Task 8."""
import typer

def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def _stub() -> None:
        """(stub — implemented in M1 Task 8)"""
        raise NotImplementedError("doctor not implemented yet")
```

- [ ] **Step 5.5: Verify CLI imports and runs --version**

```bash
.venv/bin/pkm --version
```
Expected: `pkm 0.1.0-dev`, exit 0.

```bash
.venv/bin/pkm --help
```
Expected: help text showing `init` and `doctor` subcommands.

- [ ] **Step 5.6: Commit**

```bash
git add pkm/cli.py pkm/commands/__init__.py pkm/commands/init.py pkm/commands/doctor.py
git commit -m "M1.5: CLI entry point + command stubs"
```

---

### Task 6: Templates (SCHEMA, config, settings, gitignore)

**Files:**
- Create: `pkm/templates/SCHEMA.md.template`
- Create: `pkm/templates/config.toml.template`
- Create: `pkm/templates/settings.json.template`
- Create: `pkm/templates/gitignore.template`

These are static text files copied verbatim by `pkm init`. Substitution variables (e.g., date) are minimal in V1.

#### Steps

- [ ] **Step 6.1: Make `pkm/templates/` a package** (so `importlib.resources` works)

```bash
touch pkm/templates/__init__.py
```

- [ ] **Step 6.2: Write `pkm/templates/SCHEMA.md.template`**

The full SCHEMA content lives in the spec (§4.1). Use this minimal seed in M1; it will grow in later milestones as workflows are implemented.

```markdown
# SCHEMA — hwi_PKM Operating Manual

> This file is the AI agent's entry point. Read it at the start of every PKM session.

## 1. Mission

This is a Karpathy-style **compounding wiki**. Markdown files in `data/` are the source of truth. The AI agent operates the system via the deterministic `pkm` CLI.

## 2. Layout

```
data/
├── log.md                # append-only event log
├── index.md              # auto-generated TOC
├── raw/
│   ├── captures/         # AI-driven single-note captures (with URL/summary)
│   └── chunks/           # User-curated topic folders (multi-source)
├── wiki/                 # canonical, embedded knowledge
│   ├── concepts/
│   ├── entities/
│   ├── notes/
│   └── reports/
└── writing/              # AI synthesis workspace
```

## 3. Frontmatter (M1 placeholder — full schemas in M4)

Every markdown file under `data/` carries YAML frontmatter. The full per-bucket schemas land in M4 (`pkm lint`). For now, treat any frontmatter as opaque metadata.

## 4. Workflows

(Empty in M1. Populated as commands land in M2–M6.)

## 5. CLI Reference

(Empty in M1. `pkm --help` is authoritative.)

## 6. Invariants

- **Files = truth.** Don't edit `.pkm/index.db`; it's regenerated.
- **Raw immutability.** Files under `data/raw/` are immutable after `status: reviewed`. Updates go through new captures or wiki edits.
- **No direct wiki writes (M4+).** Use `pkm promote` or `pkm wiki edit`. (Enforced by `.claude/settings.json` deny rules from M4.)

## 7. Anti-patterns

- Editing `.pkm/index.db` by hand.
- Writing to `data/wiki/**` directly without going through `pkm promote`.
- Asserting facts in `/ask` answers without citations to wiki paths.
```

- [ ] **Step 6.3: Write `pkm/templates/config.toml.template`**

```toml
# .pkm/config.toml — committed, public defaults.
# DO NOT put `exec`, `env`, credentials, or absolute paths here.
# Use .pkm/config.local.toml for those (gitignored).

[ai_cli]
# Name of the AI CLI command alias to use by default. Definitions live in
# .pkm/config.local.toml. Empty = autodetect from PATH (claude/codex/gemini).
default = ""
fallback_order = []

[indexing]
embed_captures = false
embed_chunks   = false
batch_size     = 16

[memory]
auto_throttle   = true
low_memory_mode = false
```

- [ ] **Step 6.4: Write `pkm/templates/settings.json.template`**

This is the strict `.claude/settings.json` (spec §4.3 mode 1). The deny rules for `data/wiki/**` activate in M4 once promote/wiki-edit exist; the entry is harmless before then.

```json
{
  "permissions": {
    "allow": [
      "Bash(pkm *)",
      "Read(./**)",
      "Write(./data/raw/**)", "Edit(./data/raw/**)",
      "Write(./data/writing/**)", "Edit(./data/writing/**)",
      "WebFetch", "WebSearch"
    ],
    "ask": [
      "Bash(rm *)",
      "Bash(git push *)"
    ],
    "deny": [
      "Write(./data/wiki/**)", "Edit(./data/wiki/**)",
      "Bash(pkm * --no-git*)"
    ]
  }
}
```

- [ ] **Step 6.5: Write `pkm/templates/gitignore.template`**

This is the `.gitignore` placed *inside the user's PKM repo* by `pkm init`. (Different from this dev repo's own `.gitignore` from Task 1.)

```gitignore
/dashboard/
/.pkm/index.db
/.pkm/cache/
/.pkm/config.local.toml
/.claude/settings.local.json
__pycache__/
.venv/
*.pyc
.DS_Store
```

- [ ] **Step 6.6: Commit**

```bash
git add pkm/templates/
git commit -m "M1.6: SCHEMA / config / settings / gitignore templates"
```

---

### Task 7: `pkm init` command (TDD)

**Files:**
- Modify: `pkm/commands/init.py` (replace stub with real impl)
- Test: `tests/test_init.py`

`pkm init` creates the directory layout from spec §2 and seeds it with the templates from Task 6.

Behavior:
- If target dir contains `data/` or `.pkm/` already → refuse with `STATE_ERROR` unless `--force`
- Creates: `data/`, `data/raw/captures/`, `data/raw/chunks/`, `data/wiki/{concepts,entities,notes,reports}/`, `data/writing/`, `.pkm/`, `.claude/commands/`, `data/log.md` (empty), `data/index.md` (header), `SCHEMA.md`, `.pkm/config.toml`, `.claude/settings.json`, `.gitignore`
- Prints summary on success

#### Steps

- [ ] **Step 7.1: Write the failing tests `tests/test_init.py`**

```python
"""Tests for pkm.commands.init."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _expected_paths(root: Path) -> list[Path]:
    return [
        root / "data" / "log.md",
        root / "data" / "index.md",
        root / "data" / "raw" / "captures",
        root / "data" / "raw" / "chunks",
        root / "data" / "wiki" / "concepts",
        root / "data" / "wiki" / "entities",
        root / "data" / "wiki" / "notes",
        root / "data" / "wiki" / "reports",
        root / "data" / "writing",
        root / ".pkm" / "config.toml",
        root / ".claude" / "settings.json",
        root / ".claude" / "commands",
        root / "SCHEMA.md",
        root / ".gitignore",
    ]


def test_init_in_empty_dir(tmp_path: Path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    for p in _expected_paths(tmp_path):
        assert p.exists(), f"missing: {p}"


def test_init_refuses_existing_data(tmp_path: Path):
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "STATE_ERROR" in result.output or "exists" in result.output.lower()


def test_init_force_overrides_existing(tmp_path: Path):
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "data" / "log.md").exists()


def test_init_json_output(tmp_path: Path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "path" in payload


def test_init_log_md_is_empty_or_header_only(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    log_text = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # log.md is append-only; init may seed a header line, but no events yet.
    lines = [l for l in log_text.splitlines() if l.strip()]
    assert len(lines) <= 1  # header at most


def test_init_index_md_has_header(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    idx = (tmp_path / "data" / "index.md").read_text(encoding="utf-8")
    assert idx.startswith("# Index")


def test_init_config_toml_has_indexing_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[indexing]" in cfg
    assert "[memory]" in cfg
```

- [ ] **Step 7.2: Run tests — should fail (stub raises NotImplementedError)**

```bash
.venv/bin/pytest tests/test_init.py -v
```
Expected: failures with NotImplementedError or exit_code mismatch.

- [ ] **Step 7.3: Replace `pkm/commands/init.py` with real implementation**

```python
"""`pkm init` — scaffold a fresh PKM repository.

Spec reference: §2 (layout), §3.2 (init command).
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import typer

from pkm.errors import PKMStateError

# All directories that init must create (relative to root).
_DIRS = [
    "data/raw/captures",
    "data/raw/chunks",
    "data/wiki/concepts",
    "data/wiki/entities",
    "data/wiki/notes",
    "data/wiki/reports",
    "data/writing",
    ".pkm",
    ".claude/commands",
]

# (target_relative_path, template_resource_name)
_FILES_FROM_TEMPLATES: list[tuple[str, str]] = [
    ("SCHEMA.md", "SCHEMA.md.template"),
    (".pkm/config.toml", "config.toml.template"),
    (".claude/settings.json", "settings.json.template"),
    (".gitignore", "gitignore.template"),
]


def _load_template(name: str) -> str:
    return resources.files("pkm.templates").joinpath(name).read_text(encoding="utf-8")


def _do_init(root: Path, force: bool) -> dict:
    if (root / "data").exists() or (root / ".pkm").exists():
        if not force:
            raise PKMStateError(
                f"PKM already exists at {root} (data/ or .pkm/ present)",
                hint="Use --force to overwrite, or pick an empty directory.",
            )

    for rel in _DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    # Seed log.md (empty) and index.md (header)
    (root / "data" / "log.md").write_text("", encoding="utf-8")
    (root / "data" / "index.md").write_text(
        "# Index\n\n_Auto-maintained TOC. Do not edit by hand._\n",
        encoding="utf-8",
    )

    for rel, template in _FILES_FROM_TEMPLATES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_load_template(template), encoding="utf-8")

    return {"ok": True, "path": str(root.resolve())}


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init_cmd(
        root: Path = typer.Option(
            Path("."),
            "--root",
            "-r",
            help="Target directory (default: current).",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Overwrite even if data/ or .pkm/ already exists.",
        ),
        json_out: bool = typer.Option(
            False,
            "--json",
            help="Emit a JSON summary instead of human-readable text.",
        ),
    ) -> None:
        """Scaffold a new PKM repository (data/, .pkm/, SCHEMA.md, .claude/)."""
        try:
            result = _do_init(root, force=force)
        except PKMStateError as e:
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
            typer.echo(f"Initialized PKM at {result['path']}")
            typer.echo("Next: edit SCHEMA.md, then `pkm doctor` to verify.")
```

- [ ] **Step 7.4: Run tests — should pass**

```bash
.venv/bin/pytest tests/test_init.py -v
```
Expected: 7 passed.

- [ ] **Step 7.5: Manual smoke test in /tmp**

```bash
mkdir -p /tmp/pkm-smoke && cd /tmp/pkm-smoke
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm init
ls -la
ls data/
cat .pkm/config.toml | head -5
cd -
rm -rf /tmp/pkm-smoke
```
Expected: directory tree created, config has `[indexing]` section.

- [ ] **Step 7.6: Commit**

```bash
git add pkm/commands/init.py tests/test_init.py
git commit -m "M1.7: pkm init — scaffold a fresh PKM (TDD)"
```

---

### Task 8: `pkm doctor` command (TDD basic)

**Files:**
- Modify: `pkm/commands/doctor.py` (replace stub)
- Test: `tests/test_doctor.py`

V1 doctor in M1 only checks **structure + Python version**. Model and AI-CLI checks land in M3/M5; index check in M3. The exit-code policy is locked in now (always 0 unless `--strict`) per spec §5.7.

#### Steps

- [ ] **Step 8.1: Write the failing tests `tests/test_doctor.py`**

```python
"""Tests for pkm.commands.doctor (M1 scope: structure + python only)."""
from __future__ import annotations
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _init_pkm(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_doctor_on_initialized_repo_passes(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0
    # All structure items expected to be OK
    assert "data/" in result.output
    assert "OK" in result.output


def test_doctor_on_empty_dir_reports_missing_but_exits_zero(tmp_path: Path):
    """Per spec §5.7: doctor default = exit 0 even when items missing."""
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0  # default = informative, not gate
    assert "MISSING" in result.output or "missing" in result.output.lower()


def test_doctor_strict_mode_exits_nonzero_on_missing(tmp_path: Path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert result.exit_code != 0


def test_doctor_strict_on_initialized_repo_exits_zero(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert result.exit_code == 0


def test_doctor_json_output_contract(tmp_path: Path):
    """Per spec §5.7: doctor --json must NOT include exec, env, absolute paths,
    or credentials. Whitelist: ok, items[].{name,status,detail}, system.{...}.
    """
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "items" in payload
    assert isinstance(payload["items"], list)
    for item in payload["items"]:
        assert set(item.keys()) <= {"name", "status", "detail"}
        # No absolute paths in detail
        if item["detail"]:
            assert not item["detail"].startswith("/"), \
                f"absolute path leaked: {item['detail']}"
            assert "Users/" not in item["detail"], \
                f"home dir leaked: {item['detail']}"
            assert "exec" not in item["detail"].lower()
    # System block — only allowed numeric/derived fields
    if "system" in payload:
        allowed = {"ram_total_gb", "ram_available_gb", "recommended_batch_size", "python_version"}
        assert set(payload["system"].keys()) <= allowed


def test_doctor_python_version_check(tmp_path: Path):
    _init_pkm(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.output)
    py_items = [i for i in payload["items"] if i["name"] == "python"]
    assert len(py_items) == 1
    assert py_items[0]["status"] == "ok"
```

- [ ] **Step 8.2: Run tests — should fail**

```bash
.venv/bin/pytest tests/test_doctor.py -v
```
Expected: NotImplementedError or assertion failures.

- [ ] **Step 8.3: Replace `pkm/commands/doctor.py` with real impl**

```python
"""`pkm doctor` — environment & structure health check.

Output contract (per spec §5.7):
- Default: exit 0 (status report; never gates)
- `--strict`: exit ≠ 0 if any item is missing/error
- `--json`: structured output with strict field whitelist
  - top-level: ok, items[], system{}
  - items[].{name, status, detail}; detail must NEVER include absolute paths,
    exec arrays, env values, or credentials
  - system{}: only numeric/derived fields (ram_total_gb, ram_available_gb,
    recommended_batch_size, python_version)

M1 scope: python version + repo structure. Models, AI CLI, and index checks
land in M3 / M5 / M6.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import typer

# Items expected to exist after `pkm init`. (Spec §2.)
_REQUIRED_PATHS = [
    "data/raw/captures",
    "data/raw/chunks",
    "data/wiki/concepts",
    "data/wiki/entities",
    "data/wiki/notes",
    "data/wiki/reports",
    "data/writing",
    "data/log.md",
    "data/index.md",
    ".pkm/config.toml",
    "SCHEMA.md",
    ".claude/settings.json",
]


@dataclass
class _Item:
    name: str
    status: str  # "ok" | "missing" | "error" | "optional"
    detail: str | None = None


def _check_python() -> _Item:
    v = sys.version_info
    if v >= (3, 11):
        return _Item("python", "ok", f"{v.major}.{v.minor}.{v.micro}")
    return _Item(
        "python",
        "error",
        f"requires 3.11+, found {v.major}.{v.minor}",
    )


def _check_paths(root: Path) -> list[_Item]:
    items: list[_Item] = []
    for rel in _REQUIRED_PATHS:
        target = root / rel
        if target.exists():
            items.append(_Item(rel, "ok"))
        else:
            items.append(_Item(rel, "missing"))
    return items


def _system_info() -> dict[str, object]:
    """Aggregated, sanitized system info — no absolute paths, no creds."""
    info: dict[str, object] = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    try:
        import psutil

        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / 1024**3, 1)
        info["ram_available_gb"] = round(vm.available / 1024**3, 1)
        # Recommend a conservative batch size based on available RAM
        avail_gb = info["ram_available_gb"]
        if isinstance(avail_gb, (int, float)):
            if avail_gb >= 16:
                info["recommended_batch_size"] = 32
            elif avail_gb >= 4:
                info["recommended_batch_size"] = 16
            else:
                info["recommended_batch_size"] = 4
    except ImportError:
        pass
    return info


def _render_human(items: list[_Item], system: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("[ Doctor ]")
    for it in items:
        marker = {"ok": "✓", "missing": "✗", "error": "!", "optional": "~"}[it.status]
        detail = f"  {it.detail}" if it.detail else ""
        lines.append(f"  {marker} {it.name:<30} {it.status.upper()}{detail}")
    lines.append("")
    lines.append("[ System ]")
    for k, v in system.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def doctor_cmd(
        root: Path = typer.Option(
            Path("."),
            "--root",
            "-r",
            help="PKM root (default: current directory).",
        ),
        strict: bool = typer.Option(
            False,
            "--strict",
            help="Exit non-zero if any item is missing or errored.",
        ),
        json_out: bool = typer.Option(
            False,
            "--json",
            help="Emit JSON output (strict field whitelist).",
        ),
    ) -> None:
        """Report PKM environment & structure status."""
        items: list[_Item] = []
        items.append(_check_python())
        items.extend(_check_paths(root))
        system = _system_info()

        any_bad = any(it.status in ("missing", "error") for it in items)

        if json_out:
            payload = {
                "ok": not any_bad,
                "items": [
                    {"name": it.name, "status": it.status, "detail": it.detail}
                    for it in items
                ],
                "system": system,
            }
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(_render_human(items, system))

        if strict and any_bad:
            raise typer.Exit(code=1)
```

- [ ] **Step 8.4: Run tests — should pass**

```bash
.venv/bin/pytest tests/test_doctor.py -v
```
Expected: 6 passed.

- [ ] **Step 8.5: Smoke test**

```bash
mkdir -p /tmp/pkm-doc && cd /tmp/pkm-doc
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm doctor
echo "---"
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm init
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm doctor --json | python -m json.tool
cd -
rm -rf /tmp/pkm-doc
```
Expected:
- First doctor (empty): exit 0, lots of MISSING entries
- After init, doctor --json: all `ok: true`, no absolute paths anywhere

- [ ] **Step 8.6: Commit**

```bash
git add pkm/commands/doctor.py tests/test_doctor.py
git commit -m "M1.8: pkm doctor — structure + python checks (TDD)"
```

---

### Task 9: tests/conftest.py — memory safety scaffolding

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/__init__.py`

This is the **memory safety floor** for the entire test suite (spec §8.3).
- Force `PKM_TEST_STUB_EMBEDDER=1` so accidental real-model loads fail loudly later.
- Cap virtual address space to 4 GB on Unix so a runaway test cannot OOM the host.
- Configurable cap via `PKM_TEST_RSS_CAP_GB`.

#### Steps

- [ ] **Step 9.1: Write `tests/fixtures/__init__.py` (empty marker)**

```bash
touch tests/fixtures/__init__.py
```

- [ ] **Step 9.2: Write `tests/conftest.py`**

```python
"""Pytest scaffolding — memory safety + stub embedder default.

Goals (spec §8.3):
- The fast test suite NEVER loads real ML models. Tests requiring real models
  must be `@pytest.mark.slow`, run sequentially in a separate workflow.
- A runaway test cannot crash the host. We cap virtual address space on
  Unix-like systems. Default 4 GB; override via `PKM_TEST_RSS_CAP_GB`.

This conftest runs before any test session — see pytest's discovery order.
"""
from __future__ import annotations

import os
import resource


def _apply_rss_cap() -> None:
    """Cap process virtual memory to prevent runaway tests from OOMing the host.

    Unix only. Best-effort: we lower the soft limit but never raise it.
    """
    if not hasattr(resource, "RLIMIT_AS"):
        return
    try:
        cap_gb = float(os.environ.get("PKM_TEST_RSS_CAP_GB", "4"))
    except ValueError:
        cap_gb = 4.0
    cap_bytes = int(cap_gb * 1024**3)
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)

    new_soft: int
    if soft == resource.RLIM_INFINITY:
        new_soft = cap_bytes
    else:
        new_soft = min(soft, cap_bytes)

    if hard != resource.RLIM_INFINITY and new_soft > hard:
        new_soft = hard

    try:
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))
    except (ValueError, OSError):
        # Some sandboxed environments refuse setrlimit. Don't crash the suite.
        pass


# Default the stub embedder ON — real models must be opt-in via slow tests.
os.environ.setdefault("PKM_TEST_STUB_EMBEDDER", "1")

_apply_rss_cap()
```

- [ ] **Step 9.3: Add a smoke test file `tests/test_conftest.py`**

Create a new file (do NOT append to `test_files.py`):

```python
"""Verify conftest.py scaffolding is active."""
import os


def test_stub_embedder_env_is_set():
    assert os.environ.get("PKM_TEST_STUB_EMBEDDER") == "1"


def test_rss_cap_applied_on_unix():
    """Best-effort check; Unix only."""
    import resource
    if not hasattr(resource, "RLIMIT_AS"):
        return
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    if soft == resource.RLIM_INFINITY:
        # Some sandbox refused the cap. Don't fail.
        return
    # Should be ≤ 4 GB by default
    assert soft <= 4 * 1024**3 + 1
```

- [ ] **Step 9.4: Run full suite to confirm nothing regressed**

```bash
.venv/bin/pytest -v
```
Expected: all tests pass (frontmatter 8 + files 14 + init 7 + doctor 6 + conftest 2 = 37).

- [ ] **Step 9.5: Commit**

```bash
git add tests/conftest.py tests/fixtures/__init__.py tests/test_conftest.py
git commit -m "M1.9: conftest with RSS cap + stub-embedder default"
```

---

### Task 10: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

#### Steps

- [ ] **Step 10.1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  fast:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install ${{ matrix.python-version }}

      - name: Install deps
        run: uv sync --all-extras

      - name: Lint (ruff)
        run: uv run ruff check pkm tests

      - name: Type check (pyright)
        run: uv run pyright

      - name: Fast tests
        run: uv run pytest -n auto -m "not slow"

      - name: Smoke — pkm init + doctor in tmpdir
        run: |
          mkdir /tmp/pkm-smoke
          cd /tmp/pkm-smoke
          uv --project ${{ github.workspace }} run pkm init
          uv --project ${{ github.workspace }} run pkm doctor --strict
```

> Slow workflow (`pytest -m slow -n 0 --forked --timeout=600`) lands in M3 once real models are introduced. This file is intentionally fast-only for M1.

- [ ] **Step 10.2: Verify YAML parses**

```bash
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no exception.

- [ ] **Step 10.3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "M1.10: CI workflow — ruff + pyright + fast tests + init smoke"
```

---

### Task 11: M1 verification & milestone tag

#### Steps

- [ ] **Step 11.1: Run lint + type + tests locally**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/pyright
.venv/bin/pytest -v
```
Expected: ruff clean, pyright clean (or only known-warning-level issues), all tests pass.

- [ ] **Step 11.2: End-to-end smoke**

```bash
mkdir -p /tmp/pkm-m1-final && cd /tmp/pkm-m1-final
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm init
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm doctor
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm doctor --strict
/Users/ad03159868/Downloads/Claude_lab/hwi_PKM/.venv/bin/pkm doctor --json | python -m json.tool
ls -la
ls data/wiki/
cat SCHEMA.md | head -10
cd -
rm -rf /tmp/pkm-m1-final
```
Expected: each command succeeds, exit 0 for both default and `--strict` doctor, JSON output passes structural checks.

- [ ] **Step 11.3: Tag milestone**

```bash
git tag -a m1-foundation -m "M1: Foundation complete — pkm init + doctor + test scaffold"
```

- [ ] **Step 11.4: Update `README.md` checklist** (mark M1 done)

In `README.md`, change `- [ ] M1 — Foundation` to `- [x] M1 — Foundation`.

```bash
git add README.md
git commit -m "M1.11: mark M1 complete in README"
```

---

## Acceptance criteria for M1

All of the following must hold before declaring M1 done:

- [ ] `uv sync --all-extras` succeeds on a fresh checkout.
- [ ] `pkm --version` prints `pkm 0.1.0-dev`.
- [ ] `pkm --help` shows `init` and `doctor` subcommands with help text.
- [ ] `pkm init` in an empty dir creates the full layout from spec §2 and seeds SCHEMA.md / config.toml / settings.json / .gitignore.
- [ ] `pkm init` refuses to overwrite an existing PKM unless `--force`.
- [ ] `pkm init --json` emits a single-line JSON object with `{"ok": true, "path": ...}`.
- [ ] `pkm doctor` exits 0 even when items are missing (informative).
- [ ] `pkm doctor --strict` exits non-zero on missing items, 0 on a healthy repo.
- [ ] `pkm doctor --json` output passes the field whitelist (no absolute paths, no exec, no env, no credentials).
- [ ] All tests pass: `pytest -v` shows 37 passed (frontmatter 8 + files 14 + init 7 + doctor 6 + conftest 2).
- [ ] `ruff check` and `pyright` are clean.
- [ ] CI workflow file is valid YAML; pushed to a branch, CI succeeds (verify after pushing if remote exists).
- [ ] Conftest enforces `PKM_TEST_STUB_EMBEDDER=1` and (on Unix) caps RLIMIT_AS to 4 GB.
- [ ] `git log` shows 11 clean commits, one per task, with `M1.<N>:` prefixes.
- [ ] `git tag` shows `m1-foundation` annotated.

---

## Definition of Done

The next milestone (M2 — Capture & Chunks) can begin from a clean checkout with:
1. `git clone <repo>`
2. `uv sync --all-extras`
3. `pkm init` (in a test directory)

…and proceed to add `pkm capture *` / `pkm chunks *` commands by extending `pkm/commands/`. M1 has provided the scaffolding, primitives, and test discipline that M2 will build on without revisiting infrastructure.

---

## Notes for the executor

- **Skill priorities** (apply where relevant):
  - `superpowers:test-driven-development` — Tasks 3, 4, 7, 8 are TDD. Write the test first, run it red, implement, run green, commit.
  - `superpowers:verification-before-completion` — run the exact verification commands shown before claiming a task is done.
- **DRY**: don't duplicate the Python version check or the path-list between `init.py` and `doctor.py`. If you find yourself doing so, extract a helper into `pkm/store/files.py` or a new `pkm/_layout.py`. (Up to your judgement; M1 doesn't strictly require this.)
- **YAGNI**: don't add features not listed here. No "while I'm in there, let me also…" — log it for M2 instead.
- **Commit frequency**: after every task, never larger. The 11-commit shape lets the reviewer step through them in order.
- **Ask, don't guess**: if anything in the spec contradicts this plan, surface it rather than picking a side. The spec is the source of truth.
- **For M2 planner (note)**: `pyproject.toml` declares `pkm = "pkm.cli:app"`, which bypasses the `main()` wrapper in `pkm/cli.py` that converts `PKMError` to a clean stderr message + exit 1. M1 is fine because `init`/`doctor` each handle their own errors. When M2+ adds many commands, switch the script to `pkm = "pkm.cli:main"` to centralize the error→stderr/exit conversion. (Tracking this here so M2 plan picks it up.)
