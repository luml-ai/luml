import base64
import json
from datetime import datetime
from typing import Any


class Cursor:
    _CREATED_AT_KEY = "created_at"

    def __init__(
        self,
        id: str,  # noqa: A002
        value: Any,  # noqa: ANN401
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> None:
        if order not in ("asc", "desc"):
            raise ValueError(f"order must be 'asc' or 'desc', got {order!r}")

        self.id = id
        self.value = value
        self.sort_by = sort_by
        self.order = order

    def validate_for(self, sort_by: str, order: str) -> "Cursor | None":
        if self.sort_by == sort_by and self.order == order:
            return self
        return None

    def encode(self) -> str:
        value = self.value
        if isinstance(value, datetime):
            value = value.isoformat()
        return base64.urlsafe_b64encode(
            json.dumps([self.id, value, self.sort_by, self.order]).encode()
        ).decode()

    @classmethod
    def decode(cls, cursor_str: str | None) -> "Cursor | None":
        if not cursor_str:
            return None
        try:
            cursor_id, cursor_value, sort_by, order = json.loads(
                base64.urlsafe_b64decode(cursor_str.encode()).decode()
            )
            if sort_by == cls._CREATED_AT_KEY and isinstance(cursor_value, str):
                cursor_value = datetime.fromisoformat(cursor_value)
            return cls(id=cursor_id, value=cursor_value, sort_by=sort_by, order=order)
        except Exception:
            return None

    @classmethod
    def build(
        cls,
        items: list[Any],
        limit: int,
        sort_by: str = _CREATED_AT_KEY,
        order: str = "desc",
        json_sort_column: str | None = None,
    ) -> "Cursor | None":
        if len(items) <= limit:
            return None

        cursor_rec = items[limit - 1]

        if json_sort_column:
            field_val = getattr(cursor_rec, json_sort_column, None)
            value = field_val.get(sort_by) if field_val else None
        else:
            value = getattr(cursor_rec, sort_by, None)
        return cls(id=cursor_rec.id, value=value, sort_by=sort_by, order=order)

    @classmethod
    def get_cursor(
        cls,
        items: list[Any],
        limit: int,
        sort_by: str = _CREATED_AT_KEY,
        order: str = "desc",
        json_sort_column: str | None = None,
    ) -> str | None:
        cursor = cls.build(items, limit, sort_by, order, json_sort_column)
        return cursor.encode() if cursor else None

    @classmethod
    def decode_and_validate(
        cls, cursor_str: str | None, sort_by: str, order: str
    ) -> "Cursor | None":
        cursor = cls.decode(cursor_str)
        return cursor.validate_for(sort_by, order) if cursor else None
