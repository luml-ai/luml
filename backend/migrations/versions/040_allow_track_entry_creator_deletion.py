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

UNKNOWN_AUTHOR = "Unknown user"


def upgrade() -> None:
    op.add_column(
        "track_entries", sa.Column("added_by_name", sa.String(), nullable=True)
    )
    op.execute(
        "UPDATE track_entries e SET added_by_name = u.full_name "
        "FROM users u WHERE u.id = e.added_by AND u.full_name IS NOT NULL"
    )
    op.execute(
        sa.text(
            "UPDATE track_entries SET added_by_name = :author "
            "WHERE added_by_name IS NULL"
        ).bindparams(author=UNKNOWN_AUTHOR)
    )
    op.drop_column("track_entries", "added_by")
    op.alter_column(
        "track_entries",
        "added_by_name",
        new_column_name="added_by",
        existing_type=sa.String(),
        nullable=False,
        server_default=UNKNOWN_AUTHOR,
    )


def downgrade() -> None:
    entries = op.get_bind().scalar(sa.text("SELECT count(*) FROM track_entries"))
    if entries:
        raise RuntimeError(
            f"{entries} track entries only carry an author name, "
            "added_by cannot be restored"
        )
    op.drop_column("track_entries", "added_by")
    op.add_column("track_entries", sa.Column("added_by", sa.UUID(), nullable=False))
    op.create_foreign_key(
        "track_entries_added_by_fkey",
        "track_entries",
        "users",
        ["added_by"],
        ["id"],
    )
