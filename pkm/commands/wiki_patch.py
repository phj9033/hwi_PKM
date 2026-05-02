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

# Reuse the wikilink check from commands/wiki.py to avoid duplication
from pkm.commands.wiki import _all_wiki_slugs, _check_wikilinks
from pkm.errors import PKMError, PKMValidationError
from pkm.store.frontmatter import parse
from pkm.store.frontmatter_schemas import validate_wiki
from pkm.store.log import LogEvent


def _git(
    args: list[str],
    *,
    cwd: Path,
    check: bool,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        input=stdin,
        check=check,
        capture_output=True,
        text=True,
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
