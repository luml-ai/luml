from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from luml_prisma.models.base import Base, _now_utc, _uuid_pk


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
    auto_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
