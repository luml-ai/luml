import uuid

import uuid6
from sqlalchemy import UUID, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dataforce_studio.models.base import Base


class TokenBlackListOrm(Base):
    __tablename__ = "token_black_list"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7
    )
    token: Mapped[str] = mapped_column(String, nullable=False)
    expire_at: Mapped[int] = mapped_column(Integer, nullable=False)
