import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base
from luml.schemas.live_session import LiveSession


class LiveSessionOrm(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orbits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    relay_id: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    connected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )

    def to_live_session(self) -> LiveSession:
        return LiveSession.model_validate(self)
