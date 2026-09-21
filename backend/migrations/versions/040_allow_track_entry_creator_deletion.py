"""Allow track entry creator deletion

Revision ID: 040
Revises: 039
Create Date: 2026-09-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "track_entries", sa.Column("added_by_user", sa.String(), nullable=True)
    )
    op.execute(
        "UPDATE track_entries e SET added_by_user = u.full_name "
        "FROM users u WHERE u.id = e.added_by"
    )
    op.drop_constraint(
        "track_entries_added_by_fkey", "track_entries", type_="foreignkey"
    )
    op.alter_column("track_entries", "added_by", nullable=True)
    op.create_foreign_key(
        "track_entries_added_by_fkey",
        "track_entries",
        "users",
        ["added_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    orphaned = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM track_entries WHERE added_by IS NULL")
    )
    if orphaned:
        raise RuntimeError(
            f"{orphaned} track entries were added by deleted users, "
            "reassign them before downgrading"
        )
    op.drop_constraint(
        "track_entries_added_by_fkey", "track_entries", type_="foreignkey"
    )
    op.alter_column("track_entries", "added_by", nullable=False)
    op.create_foreign_key(
        "track_entries_added_by_fkey",
        "track_entries",
        "users",
        ["added_by"],
        ["id"],
    )
    op.drop_column("track_entries", "added_by_user")
