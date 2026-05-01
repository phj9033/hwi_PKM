"""Heading-aware markdown chunker (master spec §5.3).

Algorithm:
  1. strip frontmatter (delegated to pkm.store.frontmatter.parse)
  2. walk the body line-by-line, tracking the current heading_path
  3. accumulate text under each heading
  4. when a section exceeds target_tokens (or ~target_tokens*1.4 chars for
     Korean-heavy text), split on the nearest sentence boundary, keeping a
     15%-token overlap with the previous chunk.

Token counting is a rough estimate — split() word count for ASCII, char/2 for
Korean. Good enough for batching; semantic accuracy comes from the embedder.

Sentence boundaries: English [.!?。] followed by whitespace, OR Korean
종결어미 endings 다라네요까 followed by '.' and whitespace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pkm.store.frontmatter import parse as parse_frontmatter

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_SENT_BOUNDARY = re.compile(r"(?<=[.!?。])\s+|(?<=[다라네요까]\.)\s+")
_KOREAN_RE = re.compile(r"[가-힣]")


@dataclass
class Chunk:
    chunk_idx: int
    heading_path: list[str] = field(default_factory=list)
    text: str = ""
    token_count: int = 0


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ASCII words + Korean chars/2."""
    if not text:
        return 0
    korean_chars = sum(1 for ch in text if bool(_KOREAN_RE.fullmatch(ch)))
    other = text.replace("\n", " ").split()
    return len(other) + korean_chars // 2


def _split_on_sentences(text: str) -> list[str]:
    parts = _SENT_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


def split_markdown(text: str, target_tokens: int = 500, overlap: float = 0.15) -> list[Chunk]:
    """Split a markdown document into Chunks.

    Args:
        text: full document text (may include frontmatter)
        target_tokens: soft cap per chunk
        overlap: fraction of tokens repeated across split boundaries

    Returns:
        List[Chunk] in document order. Empty list for empty input.
    """
    if not text.strip():
        return []
    _, body = parse_frontmatter(text) if text.startswith("---\n") else ({}, text)
    body = body.strip()
    if not body:
        return []

    # Phase 1: walk lines, group into (heading_path, section_text) sections.
    sections: list[tuple[list[str], str]] = []
    current_path: list[str] = []
    current_lines: list[str] = []
    for line in body.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                sections.append((list(current_path), "\n".join(current_lines).strip()))
                current_lines = []
            level = len(m.group(1))
            title = m.group(2)
            current_path = current_path[: level - 1] + [title]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((list(current_path), "\n".join(current_lines).strip()))

    # Phase 2: split oversized sections on sentence boundaries with overlap.
    chunks: list[Chunk] = []
    idx = 0
    overlap_tokens = max(1, int(target_tokens * overlap))
    for path, sec_text in sections:
        if not sec_text:
            continue
        if _estimate_tokens(sec_text) <= target_tokens:
            chunks.append(Chunk(idx, path, sec_text, _estimate_tokens(sec_text)))
            idx += 1
            continue
        # Sentence-aware split with overlap
        sentences = _split_on_sentences(sec_text)
        # If a "sentence" is itself oversized, further split it by words.
        expanded: list[str] = []
        for sent in sentences:
            if _estimate_tokens(sent) <= target_tokens:
                expanded.append(sent)
            else:
                words = sent.split()
                start = 0
                while start < len(words):
                    expanded.append(" ".join(words[start : start + target_tokens]))
                    start += target_tokens
        sentences = expanded

        buf: list[str] = []
        buf_tokens = 0
        for sent in sentences:
            t = _estimate_tokens(sent)
            if buf_tokens + t > target_tokens and buf:
                joined = " ".join(buf)
                chunks.append(Chunk(idx, path, joined, _estimate_tokens(joined)))
                idx += 1
                # Carry overlap_tokens worth of trailing sentences into the next buffer
                carry: list[str] = []
                carry_tokens = 0
                for prev in reversed(buf):
                    pt = _estimate_tokens(prev)
                    if carry_tokens + pt > overlap_tokens:
                        break
                    carry.insert(0, prev)
                    carry_tokens += pt
                buf = carry + [sent]
                buf_tokens = carry_tokens + t
            else:
                buf.append(sent)
                buf_tokens += t
        if buf:
            joined = " ".join(buf)
            chunks.append(Chunk(idx, path, joined, _estimate_tokens(joined)))
            idx += 1
    return chunks
