import uuid
from typing import Any

from sqlalchemy import UUID, CheckConstraint, ForeignKey, String, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from luml.models.base import Base, TimestampMixin
from luml.models.model_artifacts import ModelArtifactOrm
from luml.models.satellite import SatelliteOrm
from luml.schemas.deployment import Deployment


class DeploymentOrm(TimestampMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','active','failed',"
            "'deletion_pending', 'not_responding', 'deletion_failed')",
            name="deployments_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    satellite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("satellites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    satellite_name: Mapped[str] = column_property(
        select(SatelliteOrm.name)
        .where(SatelliteOrm.id == satellite_id)
        .scalar_subquery()
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_artifact_name: Mapped[str] = column_property(
        select(ModelArtifactOrm.model_name)
        .where(ModelArtifactOrm.id == model_id)
        .scalar_subquery()
    )
    collection_id: Mapped[uuid.UUID] = column_property(
        select(ModelArtifactOrm.collection_id)
        .where(ModelArtifactOrm.id == model_id)
        .scalar_subquery()
    )
    inference_url: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending"
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    dynamic_attributes_secrets: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict, server_default="{}"
    )
    env_variables_secrets: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict, server_default="{}"
    )
    env_variables: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict, server_default="{}"
    )
    satellite_parameters: Mapped[dict[str, int | str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict, server_default="{}"
    )
    schemas: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True, default=None
    )
    error_message: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True, default=None
    )
    created_by_user: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(
        postgresql.JSONB, nullable=True, default=list
    )

    orbit = relationship("OrbitOrm", back_populates="deployments")
    satellite = relationship("SatelliteOrm", back_populates="deployments")
    models = relationship("ModelArtifactOrm", back_populates="deployments")

    def to_deployment(self) -> Deployment:
        return Deployment.model_validate(self)
