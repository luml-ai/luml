import uuid
from typing import Any

from sqlalchemy import UUID, BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from luml.models.base import Base, TimestampMixin
from luml.schemas.artifacts import (
    Artifact,
    ArtifactDetails,
    ArtifactStatus,
)


class ArtifactOrm(TimestampMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index(
            "ix_artifacts_extra_values_gin",
            "extra_values",
            postgresql_using="gin",
        ),
        Index(
            "ix_artifacts_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
    )

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
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    extra_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
        default=ArtifactStatus.PENDING_UPLOAD.value,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)

    collection: Mapped[CollectionOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CollectionOrm", back_populates="artifacts", lazy="selectin"
    )
    deployments = relationship("DeploymentOrm", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"Artifact(id={self.id!r}, identifier={self.unique_identifier!r})"

    def to_artifact(self) -> Artifact:
        return Artifact.model_validate(self)

    def to_artifact_details(self) -> ArtifactDetails:
        return ArtifactDetails.model_validate(self)
