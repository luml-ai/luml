"""Preview payloads: the kernel-free tier every surface renders from.

A preview is a versioned envelope over primitive renderable blocks. Kinds
compose these six; none of them ships frontend code, which is what keeps a new
kind — including one a workspace defines — renderable the day it appears.

The payload is bounded, and a bounded payload that quietly dropped half a table
would be a worse lie than a small one: when the cap bites, the envelope says
`truncated` and the blocks shrink from the tail.
"""

from __future__ import annotations

import base64
import math
from collections.abc import Iterable, Sequence
from typing import Any

from lumlflow_kernel.cas import canonical_json

PREVIEW_SCHEMA_VERSION = 1
MAX_PREVIEW_BYTES = 64 * 1024
HEAD_ROWS = 20
MAX_POINTS = 1000

_MAX_CELL_CHARS = 120
_MAX_COLUMNS = 40
_SHRINK_ROUNDS = 8

Block = dict[str, Any]


def table(
    columns: Sequence[str],
    dtypes: Sequence[str],
    rows: Iterable[Sequence[Any]],
    total_rows: int,
) -> Block:
    """Head rows plus the schema and the true row count — never a row estimate."""
    kept = list(columns)[:_MAX_COLUMNS]
    width = len(kept)
    body = [[_cell(value) for value in row[:width]] for row in rows]
    return {
        "block": "table",
        "columns": kept,
        "dtypes": [str(dtype) for dtype in list(dtypes)[:width]],
        "rows": body,
        "total_rows": total_rows,
        "total_columns": len(columns),
    }


def series(name: str, points: Sequence[Any]) -> Block:
    """A curve, downsampled by stride so its shape and its ends survive."""
    return {
        "block": "series",
        "name": name,
        "points": [[index, _number(value)] for index, value in _downsample(points)],
        "total_points": len(points),
    }


def image(mime: str, data: bytes) -> Block:
    return {
        "block": "image",
        "mime": mime,
        "data": base64.b64encode(data).decode("ascii"),
    }


def markdown(text: str) -> Block:
    return {"block": "markdown", "text": text}


def kv(entries: dict[str, Any]) -> Block:
    return {"block": "kv", "entries": {str(k): _cell(v) for k, v in entries.items()}}


def file(name: str, size: int, content_type: str = "application/octet-stream") -> Block:
    return {"block": "file", "name": name, "size": size, "content_type": content_type}


def envelope(kind: str, blocks: Sequence[Block]) -> dict[str, Any]:
    """The stored payload, shrunk from the tail until it fits the cap."""
    current = list(blocks)
    truncated = False
    for _ in range(_SHRINK_ROUNDS):
        payload = _payload(kind, current, truncated)
        if len(canonical_json(payload)) <= MAX_PREVIEW_BYTES:
            return payload
        truncated = True
        current = _shrink(current)
    return _payload(kind, [kv({"preview": "too large to show"})], True)


def _payload(kind: str, blocks: Sequence[Block], truncated: bool) -> dict[str, Any]:
    return {
        "schema": PREVIEW_SCHEMA_VERSION,
        "kind": kind,
        "blocks": list(blocks),
        "truncated": truncated,
    }


def _shrink(blocks: Sequence[Block]) -> list[Block]:
    """Halve what is halvable; drop the last block once nothing else gives."""
    shrunk = []
    gave = False
    for block in blocks:
        rows = block.get("rows")
        points = block.get("points")
        if isinstance(rows, list) and len(rows) > 1:
            shrunk.append({**block, "rows": rows[: len(rows) // 2]})
            gave = True
        elif isinstance(points, list) and len(points) > 1:
            shrunk.append({**block, "points": points[: len(points) // 2]})
            gave = True
        else:
            shrunk.append(block)
    if gave or len(shrunk) <= 1:
        return shrunk
    return shrunk[:-1]


def _downsample(points: Sequence[Any]) -> list[tuple[int, Any]]:
    if len(points) <= MAX_POINTS:
        return list(enumerate(points))
    stride = math.ceil(len(points) / MAX_POINTS)
    kept = [(index, points[index]) for index in range(0, len(points), stride)]
    last = len(points) - 1
    if kept[-1][0] != last:
        # The endpoint takes the final sample's slot when the stride already
        # spent the budget: a curve's last value is the one that gets read, and
        # the cap is a cap.
        if len(kept) >= MAX_POINTS:
            kept.pop()
        kept.append((last, points[last]))
    return kept


def _cell(value: Any) -> str | int | float | bool | None:
    """One renderable scalar. Anything richer is shown as its own repr."""
    value = _unwrap(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _clip(value)
    if isinstance(value, bytes):
        return _clip(value.decode("utf-8", "replace"))
    return _clip(repr(value))


def _number(value: Any) -> float | int | None:
    value = _unwrap(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if not isinstance(value, float) or math.isfinite(value) else None


def _unwrap(value: Any) -> Any:
    """numpy scalars answer `item()`; nothing else in the preview path does."""
    item = getattr(value, "item", None)
    if item is None or getattr(value, "shape", ()) != ():
        return value
    try:
        return item()
    except (TypeError, ValueError):
        return value


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_CELL_CHARS else text[: _MAX_CELL_CHARS - 1] + "…"
