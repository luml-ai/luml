import uuid

from sqlalchemy import (
    UUID,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base, TimestampMixin
from luml.schemas.lineage import LineageEdge, LineageVia


class LineageNodeOrm(TimestampMixin, Base):
    __tablename__ = "lineage_nodes"
    __table_args__ = (
        Index(
            "uq_lineage_nodes_orbit_artifact_id",
            "orbit_id",
            "artifact_id",
            unique=True,
            postgresql_where=text("artifact_id IS NOT NULL"),
        ),
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
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    collection_name: Mapped[str | None] = mapped_column(String, nullable=True)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)


class LineageEdgeOrm(TimestampMixin, Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            name="uq_lineage_edges_source_target",
        ),
        CheckConstraint(
            "source_node_id <> target_node_id",
            name="ck_lineage_edges_distinct_nodes",
        ),
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
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lineage_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lineage_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user: Mapped[str] = mapped_column(String, nullable=False)
    created_via: Mapped[str] = mapped_column(String, nullable=False)

    def to_edge(self) -> LineageEdge:
        return LineageEdge(
            id=self.id,
            source=self.source_node_id,
            target=self.target_node_id,
            created_by_user=self.created_by_user,
            created_via=LineageVia(self.created_via),
            created_at=self.created_at,
        )


# A pair may exist in one direction only; the plain unique constraint above
# cannot see the reverse edge, this index makes the database reject it too.
Index(
    "uq_lineage_edges_undirected_pair",
    func.least(LineageEdgeOrm.source_node_id, LineageEdgeOrm.target_node_id),
    func.greatest(LineageEdgeOrm.source_node_id, LineageEdgeOrm.target_node_id),
    unique=True,
)
