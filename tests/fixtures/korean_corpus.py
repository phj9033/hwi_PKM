"""Korean fixture corpus for golden search tests.

Five wiki documents covering distinct topics + one captures doc that exists
only to verify FTS-only path. Frontmatter is minimal but valid for each schema.
"""

from __future__ import annotations

from pathlib import Path

WIKI_DOCS = {
    "data/wiki/concepts/oauth-token-storage.md": (
        "OAuth 토큰 저장",
        "ko",
        "# OAuth 토큰 저장\n\n## 보안 권고\n\n"
        "refresh token은 httpOnly secure cookie에 저장하고 access token은 "
        "메모리에만 보관한다. localStorage 사용은 XSS 위험 때문에 권장되지 않는다.\n",
    ),
    "data/wiki/concepts/transformer-attention.md": (
        "Transformer Attention",
        "en",
        "# Transformer Attention\n\n## Mechanism\n\n"
        "Self-attention computes scaled dot products between query and key "
        "vectors and uses softmax to derive weights for the value matrix.\n",
    ),
    "data/wiki/concepts/korean-tokenization.md": (
        "한국어 토크나이저",
        "ko",
        "# 한국어 토크나이저\n\n## 형태소 분석\n\n"
        "Kiwi와 KOMORAN은 한국어 형태소 분석기로, 한국어 NLP에서 토큰 단위 분리에 사용된다. "
        "FTS5 trigram은 외부 의존 없이 동작하지만 정밀도가 낮다.\n",
    ),
    "data/wiki/concepts/react-hooks.md": (
        "React Hooks",
        "en",
        "# React Hooks\n\n## useEffect\n\n"
        "useEffect lets functional components run side effects after render. "
        "The dependency array controls re-execution.\n",
    ),
    "data/wiki/concepts/database-indexing.md": (
        "Database Indexing",
        "en",
        "# Database Indexing\n\n## B-tree\n\n"
        "B-tree indexes give logarithmic lookup time on ordered keys. Hash "
        "indexes only support equality probes.\n",
    ),
}

CAPTURE_DOCS = {
    "data/raw/captures/2026-05-01-rrf-paper.md": (
        "RRF 논문 요약",
        "ko",
        '---\ntitle: "RRF 논문 요약"\nslug: 2026-05-01-rrf-paper\n'
        "status: draft\nsource_type: text\nlang: ko\n"
        "created_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "# RRF\n\nReciprocal Rank Fusion combines BM25 and vector retrieval "
        "by summing 1/(k+rank). The constant k=60 is from Cormack 2009.\n",
    ),
}


def install_corpus(root: Path) -> None:
    """Write all docs into `root`, creating parent dirs as needed."""
    for rel, (title, lang, body) in WIKI_DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        fm = f'---\ntitle: "{title}"\nlang: {lang}\nstatus: active\n---\n\n'
        p.write_text(fm + body, encoding="utf-8")
    for rel, (_, _, full_text) in CAPTURE_DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(full_text, encoding="utf-8")
