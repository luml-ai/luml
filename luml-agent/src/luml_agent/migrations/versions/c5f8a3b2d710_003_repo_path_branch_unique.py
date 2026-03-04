"""003_repo_path_branch_unique

Revision ID: c5f8a3b2d710
Revises: a7b2e1d4f309
Create Date: 2026-03-02 00:00:00.000000

Allow same repository path with different base branches by replacing
the single-column UNIQUE(path) with a composite UNIQUE(path, base_branch).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5f8a3b2d710"
down_revision: str | Sequence[str] | None = "a7b2e1d4f309"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    new_table = sa.Table(
        "repositories",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.UniqueConstraint("path", "base_branch", name="uq_repositories_path_branch"),
    )
    with op.batch_alter_table(
        "repositories",
        copy_from=new_table,
        recreate="always",
    ) as _batch_op:
        pass  # copy_from defines the target schema


def downgrade() -> None:
    old_table = sa.Table(
        "repositories",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("base_branch", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "repositories",
        copy_from=old_table,
        recreate="always",
    ) as _batch_op:
        pass  # copy_from defines the target schema
