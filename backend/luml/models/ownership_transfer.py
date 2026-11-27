import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base


class OwnershipTransferOrm(Base):
    __tablename__ = "ownership_transfers"
    __table_args__ = (
        Index(
            "uq_pending_ownership_transfer",
            "organization_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    recipient_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_members.id", ondelete="SET NULL")
    )
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    organization_name: Mapped[str] = mapped_column(String)
    sender_email: Mapped[str] = mapped_column(String)
    recipient_email: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notice_read: Mapped[bool] = mapped_column(Boolean, default=False)
