"""Shared text utilities: tokenization and chunking strategies."""

import re

_TOKEN_RE = re.compile(r"[a-z0-9_./:-]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def fixed_chunks(text: str, size: int) -> list[str]:
    """Fixed-width character windows; cheap but cuts sentences mid-way."""
    flat = " ".join(text.split())
    return [flat[i:i + size] for i in range(0, len(flat), size)] or [flat]


def paragraph_chunks(text: str) -> list[str]:
    """Paragraph-aligned chunks; keeps each idea intact."""
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p] or [text]
