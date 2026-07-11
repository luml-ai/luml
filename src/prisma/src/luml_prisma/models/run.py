from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from luml_prisma.models.base import Base, _now_utc, _uuid_pk


class RunOrm(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    repository_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    best_node_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="SET NULL"), nullable=True,
    )
    discovered_metric_keys_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)


class RunNodeOrm(Base):
    __tablename__ = "run_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False,
    )
    parent_node_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="SET NULL"), nullable=True,
    )
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    worktree_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    branch: Mapped[str] = mapped_column(Text, nullable=False, default="")
    debug_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)


class RunEdgeOrm(Base):
    __tablename__ = "run_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False,
    )
    from_node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    to_node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="auto")


class RunEventOrm(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False,
    )
    node_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="SET NULL"), nullable=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
