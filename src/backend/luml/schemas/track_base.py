from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.base import BaseOrmConfig


class TrackBase(BaseModel, BaseOrmConfig):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime | None = None
