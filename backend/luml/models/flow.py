import uuid

from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from luml.models.base import Base, TimestampMixin
from luml.models.live_session import LiveSessionOrm
from luml.schemas.flow import Flow, FlowSession

FLOW_NAME_CONSTRAINT = "flows_orbit_id_user_id_name_key"


class FlowOrm(TimestampMixin, Base):
    __tablename__ = "flows"
    __table_args__ = (
        UniqueConstraint("orbit_id", "user_id", "name", name=FLOW_NAME_CONSTRAINT),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session: Mapped[LiveSessionOrm] = relationship(lazy="joined")

    def to_flow(self) -> Flow:
        return Flow(
            id=self.id,
            orbit_id=self.orbit_id,
            user_id=self.user_id,
            name=self.name,
            session=FlowSession.model_validate(self.session.to_live_session()),
            created_at=self.created_at,
        )
