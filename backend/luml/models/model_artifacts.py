import uuid
from typing import Any

from sqlalchemy import UUID, BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from luml.models.base import Base, TimestampMixin
from luml.schemas.model_artifacts import (
    ModelArtifact,
    ModelArtifactDetails,
    ModelArtifactStatus,
)


class ModelArtifactOrm(TimestampMixin, Base):
    __tablename__ = "model_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    file_index: Mapped[dict[str, tuple[int, int]]] = mapped_column(
        JSONB, nullable=False
    )
    bucket_location: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unique_identifier: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    created_by_user: Mapped[str | None] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=ModelArtifactStatus.PENDING_UPLOAD.value,
    )

    collection: Mapped[CollectionOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CollectionOrm", back_populates="models", lazy="selectin"
    )
    deployments = relationship("DeploymentOrm", back_populates="models")

    def __repr__(self) -> str:
        return f"ModelArtifact(id={self.id!r}, identifier={self.unique_identifier!r})"

    def to_model_artifact(self) -> ModelArtifact:
        return ModelArtifact.model_validate(self)

    def to_model_artifact_details(self) -> ModelArtifactDetails:
        return ModelArtifactDetails.model_validate(self)
