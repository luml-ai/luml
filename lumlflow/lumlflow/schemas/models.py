import os
from datetime import datetime

from pydantic import BaseModel, field_validator

from lumlflow.schemas.base import BaseOrmConfig


class Model(BaseModel, BaseOrmConfig):
    id: str
    name: str
    created_at: datetime
    tags: list[str] | None = None
    path: str | None = None
    size: int | None = None
    source: str | None = None
    description: str | None = None

    @field_validator("source", mode="before")
    @classmethod
    def _extract_filename(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return os.path.basename(v) or v


class UpdateModel(BaseModel):
    name: str | None = None
    tags: list[str] | None = None
    description: str | None = None
