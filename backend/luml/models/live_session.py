import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, ColumnElement, ForeignKey, String, and_, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base
from luml.schemas.live_session import LIVE_SESSION_ENDED_AFTER, LiveSession


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
    # Kept when the orbit is reassigned; emptied only when the relay is removed,
    # which is allowed once every session on it has ended.
    relay_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("relays.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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


def live_session_unended(now: datetime) -> ColumnElement[bool]:
    """SQL form of the ended rule in `LiveSession.status`, negated."""
    last_sign_of_life = func.coalesce(
        LiveSessionOrm.last_heartbeat_at, LiveSessionOrm.started_at
    )
    return and_(
        LiveSessionOrm.ended_at.is_(None),
        last_sign_of_life >= now - LIVE_SESSION_ENDED_AFTER,
    )
