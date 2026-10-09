"""Artifact lineage.

Revision ID: 038
Revises: 037
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "038"
down_revision: str | None = "037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lineage_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orbit_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("collection_name", sa.String(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lineage_nodes_orbit_id"),
        "lineage_nodes",
        ["orbit_id"],
        unique=False,
    )
    op.create_index(
        "uq_lineage_nodes_orbit_artifact_id",
        "lineage_nodes",
        ["orbit_id", "artifact_id"],
        unique=True,
        postgresql_where=sa.text("artifact_id IS NOT NULL"),
    )

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orbit_id", sa.UUID(), nullable=False),
        sa.Column("source_node_id", sa.UUID(), nullable=False),
        sa.Column("target_node_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user", sa.String(), nullable=False),
        sa.Column("created_via", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_node_id <> target_node_id",
            name="ck_lineage_edges_distinct_nodes",
        ),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_node_id"], ["lineage_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"], ["lineage_nodes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_node_id",
            "target_node_id",
            name="uq_lineage_edges_source_target",
        ),
    )
    op.create_index(
        op.f("ix_lineage_edges_orbit_id"),
        "lineage_edges",
        ["orbit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lineage_edges_source_node_id"),
        "lineage_edges",
        ["source_node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lineage_edges_target_node_id"),
        "lineage_edges",
        ["target_node_id"],
        unique=False,
    )
    op.create_index(
        "uq_lineage_edges_undirected_pair",
        "lineage_edges",
        [
            sa.text("LEAST(source_node_id, target_node_id)"),
            sa.text("GREATEST(source_node_id, target_node_id)"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_lineage_edges_undirected_pair", table_name="lineage_edges")
    op.drop_index(op.f("ix_lineage_edges_target_node_id"), table_name="lineage_edges")
    op.drop_index(op.f("ix_lineage_edges_source_node_id"), table_name="lineage_edges")
    op.drop_index(op.f("ix_lineage_edges_orbit_id"), table_name="lineage_edges")
    op.drop_table("lineage_edges")
    op.drop_index("uq_lineage_nodes_orbit_artifact_id", table_name="lineage_nodes")
    op.drop_index(op.f("ix_lineage_nodes_orbit_id"), table_name="lineage_nodes")
    op.drop_table("lineage_nodes")
