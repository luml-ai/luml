import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from luml.schemas.general import Cursor, CursorType

METRICS_SORT_KEY = "metrics"
CREATED_AT_SORT_KEY = "created_at"


def encode_cursor(
    cursor_id: UUID, cursor_value: CursorType | None, sort_by: str
) -> str:
    if isinstance(cursor_value, datetime):
        cursor_value = cursor_value.isoformat()
    cursor_string = json.dumps([cursor_id.hex, cursor_value, sort_by])
    return base64.urlsafe_b64encode(cursor_string.encode()).decode()


def decode_cursor(cursor_str: str | None) -> None | Cursor:
    if not cursor_str:
        return None

    try:
        cursor_id, cursor_value, sort_by = json.loads(
            base64.urlsafe_b64decode(cursor_str.encode()).decode()
        )

        if sort_by == CREATED_AT_SORT_KEY and isinstance(cursor_value, str):
            cursor_value = datetime.fromisoformat(cursor_value)

        return Cursor(id=UUID(cursor_id), value=cursor_value, sort_by=sort_by)
    except Exception:
        return None


def get_cursor(
    items: list[Any], limit: int, sort_by: str, is_metric: bool = False
) -> str | None:
    if not items:
        return None

    if len(items) > limit:
        cursor_rec = items[limit - 1]

        if not is_metric:
            cursor_value = getattr(cursor_rec, sort_by, None)
        else:
            cursor_value = (
                cursor_rec.metrics.get(sort_by)
                if hasattr(cursor_rec, METRICS_SORT_KEY)
                else None
            )
        return encode_cursor(cursor_rec.id, cursor_value, sort_by)

    return None
