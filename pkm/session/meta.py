"""Session processing metadata — .pkm/sessions/<project>/<uuid>.json (gitignored)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pkm.session.adapters.base import SessionRef


def _meta_path(repo: Path, project_id: str, uuid: str) -> Path:
    return repo / ".pkm" / "sessions" / project_id / f"{uuid}.json"


def is_processed(repo: Path, project_id: str, uuid: str) -> bool:
    return _meta_path(repo, project_id, uuid).is_file()


def mark_processed(
    repo: Path, ref: SessionRef, project_id: str, *, extracted: dict, extracted_paths: list[str],
) -> Path:
    p = _meta_path(repo, project_id, ref.uuid)
    p.parent.mkdir(parents=True, exist_ok=True)
    sha = ""
    try:
        sha = hashlib.sha256(ref.transcript_path.read_bytes()).hexdigest()
    except OSError:
        pass
    payload = {
        "session_uuid": ref.uuid,
        "project_id": project_id,
        "transcript_path": str(ref.transcript_path),
        "transcript_sha256": sha,
        "transcript_message_count": ref.message_count,
        "processed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "extracted": extracted,
        "extracted_paths": extracted_paths,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def forget(repo: Path, project_id: str, uuid: str) -> bool:
    p = _meta_path(repo, project_id, uuid)
    if p.is_file():
        p.unlink()
        return True
    return False


def read_meta(repo: Path, project_id: str, uuid: str) -> dict | None:
    p = _meta_path(repo, project_id, uuid)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
