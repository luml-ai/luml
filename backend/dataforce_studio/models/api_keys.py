from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.api_keys import APIKeyCreateOut, APIKeyOut


class APIKeyOrm(TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    # expire_at: Mapped[int | None] = mapped_column(Integer, default=None)

    user: Mapped["UserOrm"] = relationship("UserOrm", back_populates="api_keys")  # type: ignore[name-defined]  # noqa: F821

    def to_api_key(self) -> APIKeyOut:
        return APIKeyOut.model_validate(self)

    def to_api_key_full(self) -> APIKeyCreateOut:
        return APIKeyCreateOut.model_validate(self)
