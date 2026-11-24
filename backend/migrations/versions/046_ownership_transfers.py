"""Add ownership transfer requests."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ownership_transfers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipient_member_id",
            sa.UUID(),
            sa.ForeignKey("organization_members.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recipient_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("organization_name", sa.String(), nullable=False),
        sa.Column("sender_email", sa.String(), nullable=False),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notice_read", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_ownership_transfers_recipient_id", "ownership_transfers", ["recipient_id"]
    )
    op.create_index(
        "uq_pending_ownership_transfer",
        "ownership_transfers",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.execute("""
        CREATE FUNCTION close_member_ownership_transfers() RETURNS trigger AS $$
        BEGIN
            UPDATE ownership_transfers SET status = 'cancelled'
            WHERE recipient_member_id = OLD.id AND status = 'pending';
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER close_member_ownership_transfers
        BEFORE DELETE ON organization_members
        FOR EACH ROW EXECUTE FUNCTION close_member_ownership_transfers()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER close_member_ownership_transfers ON organization_members")
    op.execute("DROP FUNCTION close_member_ownership_transfers()")
    op.drop_table("ownership_transfers")
