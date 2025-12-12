from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from luml.schemas.base import BaseOrmConfig


class StatsEmailSendCreate(BaseModel):
    email: EmailStr
    description: str


class StatsEmailSendOut(BaseModel, BaseOrmConfig):
    id: UUID
    email: EmailStr
    description: str
    created_at: datetime
