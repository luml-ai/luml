from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.deployment import Deployment


class DeploymentOrm(TimestampMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','active','failed','deleted')",
            name="deployments_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orbit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    satellite_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    inference_url: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending"
    )
    secrets: Mapped[dict[str, int]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
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
