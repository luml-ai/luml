import uuid
from datetime import datetime
from typing import Any

import uuid6
from sqlalchemy import UUID, Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import text

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatelliteCapability,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)


class SatelliteOrm(TimestampMixin, Base):
    __tablename__ = "satellites"
    __table_args__ = (
        CheckConstraint(
            "(paired = false AND capabilities = '{}'::jsonb) OR "
            "(paired = true AND capabilities != '{}'::jsonb)",
            name="satellite_pairing_capabilities_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    paired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    capabilities: Mapped[dict[SatelliteCapability, dict[str, str | int] | None]] = (
        mapped_column(
            postgresql.JSONB, nullable=False, default=dict, server_default="{}"
        )
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )

    orbit = relationship("OrbitOrm", back_populates="satellites")
    tasks = relationship(
        "SatelliteQueueOrm",
        back_populates="satellite",
        cascade="all, delete, delete-orphan",
    )
    deployments = relationship(
        "DeploymentOrm",
        back_populates="satellite",
        cascade="all, delete, delete-orphan",
    )

    def to_satellite(self) -> Satellite:
        return Satellite.model_validate(self)


class SatelliteQueueOrm(TimestampMixin, Base):
    __tablename__ = "satellite_queue"
    __table_args__ = ()

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=uuid6.uuid7
    )
    satellite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("satellites.id", ondelete="CASCADE"),
        nullable=False,
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[SatelliteTaskType] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[SatelliteTaskStatus] = mapped_column(
        String, nullable=False, default="pending", server_default="pending"
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    satellite = relationship("SatelliteOrm", back_populates="tasks")
    orbit = relationship("OrbitOrm")

    def to_queue_task(self) -> SatelliteQueueTask:
        return SatelliteQueueTask.model_validate(self)
