import uuid
from datetime import datetime

from sqlalchemy import UUID, ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base
from luml.schemas.live_session import LiveSessionToken, TunnelTokenKind


class LiveSessionTokenOrm(Base):
    """A tunnel token; a launched `view` token is a viewer grant."""

    __tablename__ = "live_session_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    kind: Mapped[TunnelTokenKind] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, index=True
    )
    launched_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    destination: Mapped[str | None] = mapped_column(String, nullable=True)

    def to_live_session_token(self) -> LiveSessionToken:
        return LiveSessionToken.model_validate(self)
