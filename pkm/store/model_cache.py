"""Model cache management for pkm doctor --download.

Downloads BAAI/bge-m3 (embedder) and BAAI/bge-reranker-v2-m3 (reranker)
into ~/.cache/pkm/models/. Each model is fetched via huggingface_hub's
snapshot_download.

Test-time short-circuit: PKM_TEST_SKIP_DOWNLOAD=1 makes download_models()
return a stub-success record without touching the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODELS = ("BAAI/bge-m3", "BAAI/bge-reranker-v2-m3")
CACHE_DIR = Path.home() / ".cache" / "pkm" / "models"


@dataclass
class DownloadResult:
    name: str
    cached: bool  # True if skipped because already present
    path: str | None  # absolute path of the snapshot dir, or None if stub


def cache_dir() -> Path:
    return CACHE_DIR


def download_models() -> list[DownloadResult]:
    if os.environ.get("PKM_TEST_SKIP_DOWNLOAD") == "1":
        return [DownloadResult(name=m, cached=True, path=None) for m in MODELS]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download  # lazy import

    results: list[DownloadResult] = []
    for model in MODELS:
        target = CACHE_DIR / model.replace("/", "__")
        already = target.exists() and any(target.iterdir())
        path = snapshot_download(
            repo_id=model,
            cache_dir=str(CACHE_DIR),
        )
        results.append(DownloadResult(name=model, cached=already, path=path))
    return results
