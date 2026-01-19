from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


type CursorType = int | str | float | datetime


class Cursor(BaseModel):
    id: UUID
    value: CursorType | None
    sort_by: str = "created_at"


class PaginationParams(BaseModel):
    cursor: Cursor | None = None
    sort_by: str = "created_at"
    order: SortOrder = SortOrder.DESC
    limit: int = 100
    extra_sort_field: str | None = None


class PaginatedSequenceResponse(BaseModel):
    items: Sequence[Any]
    has_more: bool = False
