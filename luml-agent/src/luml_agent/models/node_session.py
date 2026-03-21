from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from luml_agent.models.base import Base, _now_utc, _uuid_pk


class NodeSessionOrm(Base):
    __tablename__ = "node_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("run_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_now_utc)
