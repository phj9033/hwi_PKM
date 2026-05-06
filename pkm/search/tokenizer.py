"""Tokenizer adapter — single import surface for indexing + querying.

V1 (trigram) is the default. M12 adds kiwi via the optional `[korean]` extra.

Usage:
    spec = get_tokenizer("auto")  # honors config; kiwi if available else trigram
    text_for_fts = tokenize_for_indexing(raw_text, lang=fm.get("lang"), tokenizer=spec)

Spec reference: 2026-05-06-pkm-v2-design §5.2.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_KIWI_MODULE = None  # lazy-loaded singleton
_KIWI_INSTANCE = None


@dataclass(frozen=True)
class TokenizerSpec:
    name: str
    fts5_create_args: str
    available: bool
    version: str | None


def _load_kiwi():
    """Lazy-load kiwipiepy. Cached as `_KIWI_MODULE`."""
    global _KIWI_MODULE
    if _KIWI_MODULE is not None:
        return _KIWI_MODULE
    try:
        import kiwipiepy  # noqa: F401

        _KIWI_MODULE = kiwipiepy
        return _KIWI_MODULE
    except ImportError:
        return None


def get_tokenizer(name: str = "auto") -> TokenizerSpec:
    """Return the spec for a named tokenizer.

    `auto` = kiwi if importable, else trigram.
    Unknown names silently fall back to trigram.
    """
    if name == "auto":
        return get_tokenizer("kiwi" if _load_kiwi() else "trigram")
    if name == "kiwi":
        kiwi = _load_kiwi()
        version = getattr(kiwi, "__version__", None) if kiwi else None
        return TokenizerSpec(
            name="kiwi",
            fts5_create_args="tokenize='unicode61'",
            available=kiwi is not None,
            version=version,
        )
    # trigram (default + fallback)
    return TokenizerSpec(
        name="trigram",
        fts5_create_args="tokenize='trigram'",
        available=True,
        version=None,
    )


def detect_active(conn: sqlite3.Connection) -> str:
    """Identify the active tokenizer from schema_version.

    schema_version >= 2 → kiwi (post-m002)
    Otherwise → trigram (V1).
    """
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return "trigram"
    version = int(row[0]) if row else 0
    return "kiwi" if version >= 2 else "trigram"


def tokenize_for_indexing(
    text: str, *, lang: str | None, tokenizer: TokenizerSpec
) -> str:
    """Pre-tokenize `text` for FTS5 storage. Round-trip-safe (same input → same output)."""
    if tokenizer.name != "kiwi":
        return text
    kiwi = _load_kiwi()
    if not kiwi:
        return text  # graceful fallback if extra was uninstalled mid-session
    if lang == "en":
        return text
    return pretokenize_korean(text)


def pretokenize_korean(text: str) -> str:
    """Run kiwi on text and join morphemes with whitespace.

    Public helper — m002_kiwi_tokenizer.apply imports this directly. Returns
    the input unchanged if kiwipiepy isn't importable (graceful fallback).
    """
    global _KIWI_INSTANCE
    kiwi = _load_kiwi()
    if not kiwi:
        return text
    if _KIWI_INSTANCE is None:
        _KIWI_INSTANCE = kiwi.Kiwi()  # type: ignore[attr-defined]
    tokens = _KIWI_INSTANCE.tokenize(text)
    return " ".join(t.form for t in tokens)
