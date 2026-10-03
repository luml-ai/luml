import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, ColumnElement, ForeignKey, String, and_, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base
from luml.schemas.live_session import (
    LIVE_SESSION_ENDED_AFTER,
    LiveSession,
    LiveSessionVisibility,
    viewer_idle_period,
)


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
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    visibility: Mapped[LiveSessionVisibility] = mapped_column(String, nullable=False)
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
    last_viewer_activity_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )

    def to_live_session(self) -> LiveSession:
        return LiveSession.model_validate(self)


def live_session_implied_end() -> ColumnElement[datetime | None]:
    """SQL form of `LiveSession.implied_end`."""
    started_at = LiveSessionOrm.started_at
    return func.least(
        func.coalesce(LiveSessionOrm.last_heartbeat_at, started_at)
        + LIVE_SESSION_ENDED_AFTER,
        func.coalesce(LiveSessionOrm.last_viewer_activity_at, started_at)
        + viewer_idle_period(),
    )


def live_session_end() -> ColumnElement[datetime | None]:
    """When the session ended or will end, recorded or implied."""
    return func.coalesce(LiveSessionOrm.ended_at, live_session_implied_end())


def live_session_unended(now: datetime) -> ColumnElement[bool]:
    """SQL form of the ended rule in `LiveSession.status`, negated."""
    return and_(LiveSessionOrm.ended_at.is_(None), live_session_implied_end() >= now)


def live_session_visible_to(user_id: uuid.UUID) -> ColumnElement[bool]:
    """SQL form of `LiveSession.is_visible_to`."""
    return and_(
        LiveSessionOrm.visibility == LiveSessionVisibility.OWNER,
        LiveSessionOrm.user_id == user_id,
    )
