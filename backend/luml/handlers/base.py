import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from luml.schemas.general import CursorType


class PaginationMixin:
    @staticmethod
    def encode_cursor(cursor_id: UUID, cursor_value: CursorType, sort_by: str) -> str:
        if isinstance(cursor_value, datetime):
            cursor_value = cursor_value.isoformat()
        cursor_string = json.dumps([cursor_id.hex, cursor_value, sort_by])
        return base64.urlsafe_b64encode(cursor_string.encode()).decode()

    @staticmethod
    def decode_cursor(
        cursor_str: str | None,
    ) -> tuple[None, None, None] | tuple[UUID, CursorType, str]:
        if not cursor_str:
            return None, None, None
        try:
            cursor_id, cursor_value, sort_by = json.loads(
                base64.urlsafe_b64decode(cursor_str.encode()).decode()
            )

            if sort_by == "created_at" and isinstance(cursor_value, str):
                cursor_value = datetime.fromisoformat(cursor_value)

            return UUID(cursor_id), cursor_value, sort_by
        except Exception:
            return None, None, None

    def get_cursor(self, items: list[Any], limit: int, sort_by: str) -> str | None:
        if not items or len(items) < limit:
            return None
        cursor_rec = items[-1]
        return self.encode_cursor(cursor_rec.id, getattr(cursor_rec, sort_by), sort_by)
