import uuid

from sqlalchemy import UUID, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from luml.models.base import Base, TimestampMixin
from luml.models.model_artifacts import ModelArtifactOrm
from luml.schemas.model_artifacts import Collection


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
    collection_type: Mapped[str] = mapped_column("type", String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)

    orbit: Mapped[OrbitOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm", back_populates="collections", lazy="selectin"
    )
    models: Mapped[list[ModelArtifactOrm]] = relationship(  # noqa: F821
        back_populates="collection", cascade="all, delete, delete-orphan"
    )

    total_models = column_property(
        select(func.count(ModelArtifactOrm.id))
        .where(ModelArtifactOrm.collection_id == id)
        .correlate_except(ModelArtifactOrm)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"Collection(id={self.id!r}, name={self.name!r})"

    def to_collection(self) -> Collection:
        return Collection.model_validate(self)
