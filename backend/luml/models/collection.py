import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from luml.models.artifacts import ArtifactOrm
from luml.models.base import Base, TimestampMixin
from luml.schemas.collections import Collection


class CollectionOrm(TimestampMixin, Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orbits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column("type", String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)

    orbit: Mapped[OrbitOrm] = relationship(
        "OrbitOrm", back_populates="collections", lazy="selectin"
    )
    artifacts: Mapped[list[ArtifactOrm]] = relationship(
        back_populates="collection", cascade="all, delete, delete-orphan"
    )

    total_artifacts = column_property(
        select(func.count(ArtifactOrm.id))
        .where(ArtifactOrm.collection_id == id)
        .correlate_except(ArtifactOrm)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"Collection(id={self.id!r}, name={self.name!r})"

    def to_collection(self) -> Collection:
        return Collection.model_validate(self)


if TYPE_CHECKING:
    from luml.models.orbit import OrbitOrm
