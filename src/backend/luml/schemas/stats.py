from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from luml.schemas.base import BaseOrmConfig


class StatsEmailSendCreate(BaseModel):
    email: EmailStr = Field(max_length=254)
    description: str = Field(max_length=1000)


class StatsEmailSendOut(BaseModel, BaseOrmConfig):
    id: UUID
    email: EmailStr
    description: str
    created_at: datetime
