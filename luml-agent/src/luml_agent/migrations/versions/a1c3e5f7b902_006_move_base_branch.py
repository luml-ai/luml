"""006_move_base_branch_to_task_run

Revision ID: a1c3e5f7b902
Revises: f2b7d8a1c934
Create Date: 2026-03-02 00:00:00.000000

Move base_branch from repositories to tasks and runs tables.
Each task/run now tracks its own target branch independently.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b902"
down_revision: str | Sequence[str] | None = "f2b7d8a1c934"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("base_branch", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("base_branch", sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE tasks SET base_branch = ("
            "  SELECT r.base_branch FROM repositories r"
            "  WHERE r.id = tasks.repository_id"
            ")"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE runs SET base_branch = ("
            "  SELECT r.base_branch FROM repositories r"
            "  WHERE r.id = runs.repository_id"
            ")"
        )
    )
    conn.execute(sa.text(
        "UPDATE tasks SET base_branch = 'main'"
        " WHERE base_branch IS NULL"
    ))
    conn.execute(sa.text(
        "UPDATE runs SET base_branch = 'main'"
        " WHERE base_branch IS NULL"
    ))

    tasks_table = sa.Table(
        "tasks",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("tmux_session", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "tasks", copy_from=tasks_table, recreate="always",
    ) as _batch_op:
        pass

    runs_table = sa.Table(
        "runs",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "runs", copy_from=runs_table, recreate="always",
    ) as _batch_op:
        pass

    repos_table = sa.Table(
        "repositories",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
    )
    with op.batch_alter_table(
        "repositories", copy_from=repos_table, recreate="always",
    ) as _batch_op:
        pass


def downgrade() -> None:
    repos_table = sa.Table(
        "repositories",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("base_branch", sa.Text(), nullable=False, server_default="main"),
        sa.UniqueConstraint("path", "base_branch", name="uq_repositories_path_branch"),
    )
    with op.batch_alter_table(
        "repositories", copy_from=repos_table, recreate="always",
    ) as _batch_op:
        pass

    tasks_table = sa.Table(
        "tasks",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("tmux_session", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "tasks", copy_from=tasks_table, recreate="always",
    ) as _batch_op:
        pass

    runs_table = sa.Table(
        "runs",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "runs", copy_from=runs_table, recreate="always",
    ) as _batch_op:
        pass
