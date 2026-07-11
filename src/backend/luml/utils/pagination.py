import base64
import json
import uuid
from datetime import datetime
from enum import Enum
from uuid import UUID

from luml.schemas.general import Cursor, SortOrder

EXTRA_VALUES_SORT_KEY = "extra_values"
CREATED_AT_SORT_KEY = "created_at"

SCOPE_NAMESPACE = uuid.UUID("a8f5f167-4f8a-5e6c-9b2d-1c3e4d5a6b7f")


def _normalize_scope_part(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set, frozenset)):
        return ",".join(sorted(_normalize_scope_part(item) for item in value))
    if isinstance(value, Enum):
        return _normalize_scope_part(value.value)
    if isinstance(value, UUID):
        return value.hex
    return str(value)


def build_scope_id(**filters: object) -> UUID:
    key = "|".join(
        f"{name}={_normalize_scope_part(filters[name])}" for name in sorted(filters)
    )
    return uuid.uuid5(SCOPE_NAMESPACE, key)


def encode_cursor(cursor: Cursor | None) -> str | None:
    if cursor is None:
        return None
    value = cursor.value
    if isinstance(value, datetime):
        value = value.isoformat()
    scope_id = cursor.scope_id.hex if cursor.scope_id else None
    cursor_string = json.dumps(
        [cursor.id.hex, value, cursor.sort_by, cursor.order.value, scope_id]
    )
    return base64.urlsafe_b64encode(cursor_string.encode()).decode()


def decode_cursor(cursor_str: str | None) -> None | Cursor:
    if not cursor_str:
        return None

    try:
        parts = json.loads(base64.urlsafe_b64decode(cursor_str.encode()).decode())
        cursor_id, cursor_value, sort_by = parts[0], parts[1], parts[2]
        order = SortOrder(parts[3]) if len(parts) > 3 else SortOrder.DESC
        scope_id = UUID(parts[4]) if len(parts) > 4 and parts[4] else None

        if sort_by == CREATED_AT_SORT_KEY and isinstance(cursor_value, str):
            cursor_value = datetime.fromisoformat(cursor_value)

        return Cursor(
            id=UUID(cursor_id),
            value=cursor_value,
            sort_by=sort_by,
            order=order,
            scope_id=scope_id,
        )
    except Exception:
        return None
