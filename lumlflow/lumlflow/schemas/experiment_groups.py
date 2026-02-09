from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig


class Group(BaseModel, BaseOrmConfig):
    id: str
    name: str
    description: str | None
    created_at: datetime


class PaginatedGroups(BaseModel):
    items: list[Group]
    cursor: str | None = None


class GroupsSortBy(StrEnum):
    NAME = "name"
    DESCRIPTION = "description"
    CREATED_AT = "created_at"
