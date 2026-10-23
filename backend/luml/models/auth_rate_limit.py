from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base


class AuthRateLimitOrm(Base):
    __tablename__ = "auth_rate_limits"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
