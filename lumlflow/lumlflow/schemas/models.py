from datetime import datetime

from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig


class Model(BaseModel, BaseOrmConfig):
    id: str
    name: str
    created_at: datetime
    tags: list[str] | None = None
    path: str | None = None
