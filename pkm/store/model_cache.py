"""Model cache management for pkm doctor --download.

Downloads BAAI/bge-m3 (embedder) and BAAI/bge-reranker-v2-m3 (reranker)
into ~/.cache/pkm/models/. Each model is fetched via huggingface_hub's
snapshot_download.

`huggingface_hub.snapshot_download(cache_dir=ROOT)` writes to
``ROOT/models--<org>--<name>/`` (HF standard layout). ``model_dir()`` and
``is_cached()`` are the canonical helpers — every caller (doctor pre-flight,
bench pre-flight, rerank load) must go through them so the layout assumption
lives in exactly one place.

Test-time short-circuit: PKM_TEST_SKIP_DOWNLOAD=1 makes download_models()
return a stub-success record without touching the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODELS = ("BAAI/bge-m3", "BAAI/bge-reranker-v2-m3")
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pkm" / "models"


@dataclass
class DownloadResult:
    name: str
    cached: bool  # True if skipped because already present
    path: str | None  # absolute path of the snapshot dir, or None if stub


def cache_dir() -> Path:
    """Resolve the model cache root. ``PKM_MODEL_CACHE`` overrides the default."""
    override = os.environ.get("PKM_MODEL_CACHE")
    return Path(override) if override else _DEFAULT_CACHE_DIR


def model_dir(repo_id: str) -> Path:
    """Path that ``snapshot_download(cache_dir=cache_dir())`` writes to for ``repo_id``."""
    return cache_dir() / f"models--{repo_id.replace('/', '--')}"


def is_cached(repo_id: str) -> bool:
    """True if the model has been downloaded into the HF-layout directory."""
    target = model_dir(repo_id)
    return target.exists() and any(target.iterdir())


def download_models() -> list[DownloadResult]:
    if os.environ.get("PKM_TEST_SKIP_DOWNLOAD") == "1":
        return [DownloadResult(name=m, cached=True, path=None) for m in MODELS]

    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download  # lazy import

    results: list[DownloadResult] = []
    for model in MODELS:
        already = is_cached(model)
        path = snapshot_download(
            repo_id=model,
            cache_dir=str(root),
        )
        results.append(DownloadResult(name=model, cached=already, path=path))
    return results
