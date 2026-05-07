"""Deterministic index.md builder for data/projects/<id>/index.md."""

from __future__ import annotations

from pathlib import Path

import yaml

from pkm.store.project_paths import CATEGORIES, project_dir, project_index


def rebuild_index(repo: Path, project_id: str, *, max_per_category: int = 5) -> None:
    pdir = project_dir(repo, project_id)
    idx_path = project_index(repo, project_id)
    fm = _read_existing_frontmatter(idx_path)

    sections: list[str] = [f"# {project_id}\n"]
    sections.append(f"\n_이 페이지는 `pkm project rebuild-index {project_id}` 가 자동 갱신합니다._\n")

    for cat in CATEGORIES:
        items = sorted(
            (pdir / cat).glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:max_per_category]
        if not items:
            continue
        title_map = {
            "decisions": "핵심 결정",
            "pitfalls": "함정 / 하지 말 것",
            "snippets": "재사용 스니펫",
            "qna": "질의응답",
            "notes": "메모",
        }
        sections.append(f"\n## {title_map[cat]} ({cat}, 최근 {len(items)})\n")
        for it in items:
            t = _read_title(it) or it.stem
            rel = it.relative_to(repo)
            sections.append(f"- [{t}]({rel})")
        sections.append("")

    body = "\n".join(sections)
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) if fm else ""
    idx_path.write_text("---\n" + front + "---\n\n" + body, encoding="utf-8")


def _read_existing_frontmatter(idx_path: Path) -> dict:
    if not idx_path.is_file():
        return {}
    text = idx_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}


def _read_title(p: Path) -> str | None:
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        fm = yaml.safe_load(text[4:end]) or {}
        return fm.get("title")
    except yaml.YAMLError:
        return None
