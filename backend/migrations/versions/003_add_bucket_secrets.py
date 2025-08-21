"""Add bucket secrets

Revision ID: 003
Revises: 002
Create Date: 2025-06-15 18:36:41.539193

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bucket_secrets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("bucket_name", sa.String(), nullable=False),
        sa.Column("access_key", sa.String(), nullable=True),
        sa.Column("secret_key", sa.String(), nullable=True),
        sa.Column("session_token", sa.String(), nullable=True),
        sa.Column("secure", sa.Boolean(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("cert_check", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("orbit_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("bucket_location", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("unique_identifier", sa.String(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("orbits", sa.Column("bucket_secret_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        None,
        "orbits",
        "bucket_secrets",
        ["bucket_secret_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(None, "orbits", type_="foreignkey")
    op.drop_column("orbits", "bucket_secret_id")
    op.drop_table("ml_models")
    op.drop_table("collections")
    op.drop_table("bucket_secrets")
