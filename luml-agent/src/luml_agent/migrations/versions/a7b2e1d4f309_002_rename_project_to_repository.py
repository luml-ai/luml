"""002_rename_project_to_repository

Revision ID: a7b2e1d4f309
Revises: 3d627c3f6ecb
Create Date: 2026-03-01 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "a7b2e1d4f309"
down_revision: str | Sequence[str] | None = "3d627c3f6ecb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("projects", "repositories")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("project_id", new_column_name="repository_id")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("project_id", new_column_name="repository_id")


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("repository_id", new_column_name="project_id")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("repository_id", new_column_name="project_id")

    op.rename_table("repositories", "projects")
