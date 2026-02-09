import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from lumlflow.schemas.base import Cursor, SortOrder

CREATED_AT_SORT_KEY = "created_at"


def encode_cursor(cursor: Cursor | None) -> str | None:
    if cursor is None:
        return None
    value = cursor.value
    if isinstance(value, datetime):
        value = value.isoformat()
    cursor_string = json.dumps(
        [cursor.id.hex, value, cursor.sort_by, cursor.order.value]
    )
    return base64.urlsafe_b64encode(cursor_string.encode()).decode()


def decode_cursor(cursor_str: str | None) -> None | Cursor:
    if not cursor_str:
        return None

    try:
        parts = json.loads(base64.urlsafe_b64decode(cursor_str.encode()).decode())
        cursor_id, cursor_value, sort_by, order = parts[0], parts[1], parts[2], parts[3]

        if sort_by == CREATED_AT_SORT_KEY and isinstance(cursor_value, str):
            cursor_value = datetime.fromisoformat(cursor_value)

        return Cursor(
            id=UUID(cursor_id),
            value=cursor_value,
            sort_by=sort_by,
            order=order,
        )
    except Exception:
        return None


def get_cursor(
    items: list[Any], limit: int, sort_by: str, order: SortOrder
) -> str | None:
    if not items:
        return None

    if len(items) > limit:
        cursor_rec = items[limit - 1]

        cursor = Cursor(
            id=UUID(cursor_rec.id),
            value=getattr(cursor_rec, sort_by, None),
            sort_by=sort_by,
            order=SortOrder(order),
        )

        return encode_cursor(cursor)

    return None
