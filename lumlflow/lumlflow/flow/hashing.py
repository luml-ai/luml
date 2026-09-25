"""Canonical JSON serialization and the sha256 hashes derived from it."""

import hashlib
import json
from pathlib import Path
from typing import Any

_FILE_CHUNK_BYTES = 1 << 20


def canonical_json(value: Any) -> bytes:
    """Sorted keys, no insignificant whitespace, NaN/Infinity rejected."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_json(value: Any) -> str:
    return hash_bytes(canonical_json(value))


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_FILE_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
