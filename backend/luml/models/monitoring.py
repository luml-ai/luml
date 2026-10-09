import uuid

from sqlalchemy import UUID, Integer
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base


class MonitoringLaunchTokenOrm(Base):
    """Consumed launch-token ``jti`` values, for single-use enforcement."""

    __tablename__ = "monitoring_launch_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    jti: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    expire_at: Mapped[int] = mapped_column(Integer, nullable=False)
