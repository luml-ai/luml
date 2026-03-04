"""004_fix_repo_unique_constraint

Revision ID: e1a4d9c7b823
Revises: c5f8a3b2d710
Create Date: 2026-03-02 00:00:00.000000

Drop the old single-column UNIQUE(path) that was left behind by 003,
keeping only the composite UNIQUE(path, base_branch).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1a4d9c7b823"
down_revision: str | Sequence[str] | None = "c5f8a3b2d710"
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
        pass  # copy_from defines the exact target schema


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
        pass  # copy_from defines the exact target schema
