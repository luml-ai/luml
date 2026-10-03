import uuid
from datetime import datetime

from sqlalchemy import UUID, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base, TimestampMixin
from luml.schemas.relay import Relay, RelayStatus


class RelayOrm(TimestampMixin, Base):
    __tablename__ = "relays"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    # Empty for a managed relay, which every organization may use.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    base_domain: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    agent_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RelayStatus] = mapped_column(
        String,
        nullable=False,
        default=RelayStatus.ENABLED,
        server_default=RelayStatus.ENABLED.value,
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    previous_token_hash: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    previous_token_expires_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    connected_agents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    def to_relay(self) -> Relay:
        return Relay.model_validate(self)
