"""Install helpers — two strategies for tracking installed artifacts.

1. Embedded blocks in user-edited files (CLAUDE.md):
   <!-- pkm:start --> / <!-- pkm:end --> markers around the block.
   apply_managed_block() inserts/replaces between markers; user content outside
   is preserved.

2. Standalone files (slash commands, skill bodies):
   These start with YAML frontmatter (---\n...). An HTML comment above the
   frontmatter would break Claude Code's frontmatter parser. Instead we record
   the absolute path of every emitted file in ~/.pkm/install_manifest.json.
   Uninstall reads the manifest and deletes exactly those paths.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

BLOCK_START = "<!-- pkm:start managed by pkm install -->"
BLOCK_END = "<!-- pkm:end managed by pkm install -->"


def _manifest_path() -> Path:
    return Path.home() / ".pkm" / "install_manifest.json"


def _templates_root() -> Path:
    """Filesystem path to pkm/templates/ — robust whether installed via uv tool or wheel."""
    import pkm
    return Path(pkm.__file__).parent / "templates"


# --- Strategy 1: embedded block in user file ---------------------------------

def apply_managed_block(target: Path, block_content: str) -> None:
    """Insert or replace the managed block in target file. Preserves user content."""
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    pattern = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.DOTALL)
    if pattern.search(existing):
        new = pattern.sub(block_content.strip(), existing)
    else:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new = existing + ("\n" if existing else "") + block_content.strip() + "\n"
    target.write_text(new, encoding="utf-8")


def remove_managed_block(target: Path) -> None:
    if not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    pattern = re.compile(r"\n*" + re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n*", re.DOTALL)
    new = pattern.sub("\n", text).strip()
    if new:
        target.write_text(new + "\n", encoding="utf-8")
    else:
        target.unlink()


# --- Strategy 2: manifest-tracked standalone files ---------------------------

def read_manifest() -> list[str]:
    p = _manifest_path()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("paths", [])
    except (json.JSONDecodeError, OSError):
        return []


def write_manifest(paths: list[str]) -> None:
    p = _manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"paths": sorted(set(paths))}, indent=2), encoding="utf-8")


def install_file(template_relpath: str, target: Path) -> None:
    """Copy a template (path relative to pkm/templates/) verbatim to target.
    Records target in manifest. Always overwrites the target.
    """
    src = _templates_root() / template_relpath
    if not src.is_file():
        raise FileNotFoundError(f"template not found: {src}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    paths = read_manifest()
    abs_target = str(target.resolve())
    if abs_target not in paths:
        paths.append(abs_target)
        write_manifest(paths)


def install_dir(template_reldir: str, target_dir: Path) -> None:
    """Copy all .md files in pkm/templates/<reldir>/ recursively to target_dir."""
    src_dir = _templates_root() / template_reldir
    if not src_dir.is_dir():
        raise FileNotFoundError(f"template dir not found: {src_dir}")
    for src in src_dir.rglob("*.md"):
        rel = src.relative_to(src_dir)
        target = target_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        paths = read_manifest()
        abs_target = str(target.resolve())
        if abs_target not in paths:
            paths.append(abs_target)
            write_manifest(paths)


def uninstall_via_manifest() -> int:
    paths = read_manifest()
    removed = 0
    for p in paths:
        try:
            Path(p).unlink()
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            pass
    mp = _manifest_path()
    if mp.is_file():
        mp.unlink()
    for p in paths:
        parent = Path(p).parent
        for _ in range(4):
            try:
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break
    return removed
