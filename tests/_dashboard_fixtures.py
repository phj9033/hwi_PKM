"""Shared fixture helpers for M6 dashboard tests."""

from __future__ import annotations

from pathlib import Path


def seed(root: Path) -> None:
    """Seed a tiny corpus: 2 captures, 1 chunk, 2 wiki, 1 writing."""
    (root / "data" / "raw" / "captures").mkdir(parents=True)
    (root / "data" / "raw" / "chunks" / "oauth").mkdir(parents=True)
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "wiki" / "notes").mkdir(parents=True)
    (root / "data" / "writing").mkdir(parents=True)

    (root / "data" / "raw" / "captures" / "alpha.md").write_text(
        "---\ntitle: Alpha\nslug: alpha\nstatus: reviewed\nlang: en\n"
        "tags: [oauth]\n---\nbody alpha\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "captures" / "beta.md").write_text(
        "---\ntitle: Beta\nslug: beta\nstatus: draft\nlang: ko\n---\n본문\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "chunks" / "oauth" / "README.md").write_text(
        "---\ntopic: oauth\nstatus: collecting\nlang: en\nsources: []\n---\n\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "concepts" / "token-storage.md").write_text(
        "---\ntitle: Token Storage\nslug: token-storage\nstatus: active\nlang: en\n---\n"
        "See [[token-rotation]].\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "notes" / "token-rotation.md").write_text(
        "---\ntitle: Token Rotation\nslug: token-rotation\nstatus: active\nlang: en\n---\n"
        "Rotation policy.\n",
        encoding="utf-8",
    )
    (root / "data" / "writing" / "team-oauth-guideline.md").write_text(
        "---\ntitle: Team OAuth Guideline\nslug: team-oauth-guideline\n"
        "status: draft\nlang: en\nderived_from: [data/wiki/concepts/token-storage.md]\n"
        "---\nGuideline body.\n",
        encoding="utf-8",
    )
