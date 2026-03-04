from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


def _uuid_pk() -> str:
    return uuid4().hex


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class RepositoryOrm(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class TaskOrm(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    repository_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    worktree_path: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tmux_session: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)


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


class NodeSessionOrm(Base):
    __tablename__ = "node_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(
    dbapi_connection: Any,  # noqa: ANN401
    connection_record: Any,  # noqa: ANN401
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(db_url: str) -> Engine:
    kwargs: dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
    }
    if db_url == "sqlite://" or db_url == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(db_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(bind=engine, expire_on_commit=False)
