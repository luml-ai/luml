import uuid

from sqlalchemy import UUID, ForeignKey, Integer, String, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from luml.models.base import Base, TimestampMixin


class TrackArtifactOrm(TimestampMixin, Base):
    __tablename__ = "track_entries"
    __table_args__ = (
        UniqueConstraint(
            "track_id", "artifact_id", name="uq_track_entries_track_id_artifact_id"
        ),
        UniqueConstraint(
            "track_id", "version", name="uq_track_entries_track_id_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("track_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    track: Mapped[TrackOrm] = relationship(  # noqa: F821
        "TrackOrm", back_populates="entries", lazy="selectin"
    )
    artifact: Mapped[ArtifactOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ArtifactOrm", lazy="selectin"
    )
    stage: Mapped[TrackStageOrm | None] = relationship("TrackStageOrm", lazy="selectin")

    def __repr__(self) -> str:
        return f"TrackArtifact(id={self.id!r}, version={self.version!r})"


class TrackOrm(TimestampMixin, Base):
    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint("orbit_id", "name", name="uq_tracks_orbit_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orbits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    next_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    orbit: Mapped[OrbitOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm", back_populates="tracks", lazy="selectin"
    )
    entries: Mapped[list[TrackArtifactOrm]] = relationship(
        back_populates="track", cascade="all, delete, delete-orphan"
    )
    stages: Mapped[list[TrackStageOrm]] = relationship(
        back_populates="track",
        cascade="all, delete, delete-orphan",
        lazy="selectin",
        order_by="TrackStageOrm.created_at",
    )

    total_entries = column_property(
        select(func.count(TrackArtifactOrm.id))
        .where(TrackArtifactOrm.track_id == id)
        .correlate_except(TrackArtifactOrm)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"Track(id={self.id!r}, name={self.name!r})"


class TrackStageOrm(TimestampMixin, Base):
    __tablename__ = "track_stages"
    __table_args__ = (
        UniqueConstraint("track_id", "name", name="uq_track_stages_track_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)

    track: Mapped[TrackOrm] = relationship(  # noqa: F821
        "TrackOrm", back_populates="stages", lazy="selectin"
    )

    is_used = column_property(
        select(func.count(TrackArtifactOrm.id) > 0)
        .where(TrackArtifactOrm.stage_id == id)
        .correlate_except(TrackArtifactOrm)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"TrackStage(id={self.id!r}, name={self.name!r})"
