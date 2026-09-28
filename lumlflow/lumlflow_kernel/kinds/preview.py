"""Preview payloads: the kernel-free tier every surface renders from.

A preview is a versioned envelope over primitive renderable blocks. Kinds
compose these six; none of them ships frontend code, which is what keeps a new
kind — including one a workspace defines — renderable the day it appears.

The payload is bounded, and a bounded payload that quietly dropped half a table
would be a worse lie than a small one: when the cap bites, the envelope says
`truncated` and each block keeps a smaller renderable form.
"""

from __future__ import annotations

import base64
import io
import math
from collections.abc import Iterable, Sequence
from typing import Any

from lumlflow_kernel.cas import canonical_json

PREVIEW_SCHEMA_VERSION = 1
MAX_PREVIEW_BYTES = 64 * 1024
HEAD_ROWS = 20
MAX_POINTS = 1000
MAX_COLUMNS = 40

_MAX_CELL_CHARS = 120
_SHRINK_ROUNDS = 64
_TEXT_TRUNCATION_MARKER = "\n\n… preview truncated"

Block = dict[str, Any]


def table(
    columns: Sequence[str],
    dtypes: Sequence[str],
    rows: Iterable[Sequence[Any]],
    total_rows: int,
) -> Block:
    """Head rows plus the schema and the true row count — never a row estimate."""
    kept = list(columns)[:MAX_COLUMNS]
    width = len(kept)
    body = _normalize_rows(rows, width, clip=True)
    return {
        "block": "table",
        "columns": kept,
        "dtypes": [str(dtype) for dtype in list(dtypes)[:width]],
        "rows": body,
        "total_rows": total_rows,
        "total_columns": len(columns),
    }


def page(
    columns: Sequence[str],
    dtypes: Sequence[str],
    rows: Iterable[Sequence[Any]],
    total_rows: int,
    offset: int,
) -> dict[str, Any]:
    kept = list(columns)[:MAX_COLUMNS]
    width = len(kept)
    return {
        "columns": kept,
        "dtypes": [str(dtype) for dtype in list(dtypes)[:width]],
        "rows": _normalize_rows(rows, width, clip=False),
        "offset": offset,
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


def metric(entries: dict[str, Any]) -> Block:
    normalized: dict[str, str | int | float | bool | None] = {}
    for name, entry in entries.items():
        value = _unwrap(entry)
        if isinstance(value, float) and not math.isfinite(value):
            if math.isnan(value):
                normalized[str(name)] = "nan"
            else:
                normalized[str(name)] = "inf" if value > 0 else "-inf"
        else:
            normalized[str(name)] = _cell(value)
    return {"block": "kv", "entries": normalized}


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
        smaller = _shrink(current)
        if smaller == current:
            break
        current = smaller
    return _payload(kind, [kv({"preview": "too large to show"})], True)


def _payload(kind: str, blocks: Sequence[Block], truncated: bool) -> dict[str, Any]:
    return {
        "schema": PREVIEW_SCHEMA_VERSION,
        "kind": kind,
        "blocks": list(blocks),
        "truncated": truncated,
    }


def _shrink(blocks: Sequence[Block]) -> list[Block]:
    """Shrink each renderable shape before dropping an unshrinkable block."""
    shrunk: list[Block] = []
    gave = False
    for block in blocks:
        smaller, changed = _shrink_block(block)
        shrunk.append(smaller)
        gave = gave or changed
    if gave or len(shrunk) <= 1:
        return shrunk
    return shrunk[:-1]


def _shrink_block(block: Block) -> tuple[Block, bool]:
    if block.get("block") == "image":
        smaller = _shrink_image(block)
        if smaller is not None:
            return smaller, True

    text = block.get("text")
    if isinstance(text, str) and len(text) > 1:
        content = (
            text[: -len(_TEXT_TRUNCATION_MARKER)]
            if text.endswith(_TEXT_TRUNCATION_MARKER)
            else text
        )
        if len(content) > 1:
            kept = content[: max(len(content) // 2, 1)]
            return {**block, "text": kept + _TEXT_TRUNCATION_MARKER}, True

    entries = block.get("entries")
    if isinstance(entries, dict) and len(entries) > 1:
        limit = max(len(entries) // 2, 1)
        return {**block, "entries": dict(list(entries.items())[:limit])}, True

    rows = block.get("rows")
    if isinstance(rows, list) and len(rows) > 1:
        return {**block, "rows": rows[: len(rows) // 2]}, True

    points = block.get("points")
    if isinstance(points, list) and len(points) > 1:
        return {**block, "points": points[: len(points) // 2]}, True

    return block, False


def _shrink_image(block: Block) -> Block | None:
    data = block.get("data")
    if not isinstance(data, str):
        return None
    try:
        from PIL import Image

        source = base64.b64decode(data, validate=True)
        with Image.open(io.BytesIO(source)) as opened:
            image_format = opened.format
            if image_format is None:
                return None
            size = (max(opened.width // 2, 1), max(opened.height // 2, 1))
            resampling = getattr(Image, "Resampling", Image)
            resized = opened.resize(size, resampling.LANCZOS)
            output = io.BytesIO()
            resized.save(output, format=image_format)
    except Exception:
        return None
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    if encoded == data:
        return None
    return {**block, "data": encoded}


def _normalize_rows(
    rows: Iterable[Sequence[Any]], width: int, *, clip: bool
) -> list[list[str | int | float | bool | None]]:
    return [[_cell(value, clip=clip) for value in row[:width]] for row in rows]


def _cell(value: Any, *, clip: bool = True) -> str | int | float | bool | None:
    """One renderable scalar. Anything richer is shown as its own repr."""
    value = _unwrap(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = value
    elif isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    else:
        text = repr(value)
    return _clip(text) if clip else text


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
