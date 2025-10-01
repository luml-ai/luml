"""Change id type

Revision ID: 019
Revises: 018
Create Date: 2025-10-01 15:12:04.751010

"""
# ruff: noqa

from collections.abc import Sequence

import shortuuid
import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()

    def convert_shortuuid_to_uuid(short_uuid_str):
        try:
            if len(short_uuid_str) == 36 and "-" in short_uuid_str:
                return short_uuid_str
            return str(shortuuid.decode(short_uuid_str))
        except Exception:
            import uuid

            return str(uuid.uuid4())

    tables_to_convert = [
        "users",
        "organizations",
        "bucket_secrets",
        "orbits",
        "collections",
        "model_artifacts",
        "satellites",
        "deployments",
        "orbit_members",
        "orbit_secrets",
        "organization_members",
        "organization_invites",
        "satellite_queue",
        "stats_emails",
        "token_black_list",
    ]

    id_mapping = {}

    for table in tables_to_convert:
        result = connection.execute(sa.text(f"SELECT id FROM {table}"))
        for row in result:
            short_uuid = row[0]
            standard_uuid = convert_shortuuid_to_uuid(short_uuid)
            id_mapping[short_uuid] = standard_uuid

    op.drop_constraint(
        "bucket_secrets_organization_id_fkey", "bucket_secrets", type_="foreignkey"
    )
    op.drop_constraint("collections_orbit_id_fkey", "collections", type_="foreignkey")
    op.drop_constraint("deployments_model_id_fkey", "deployments", type_="foreignkey")
    op.drop_constraint("deployments_orbit_id_fkey", "deployments", type_="foreignkey")
    op.drop_constraint(
        "deployments_satellite_id_fkey", "deployments", type_="foreignkey"
    )
    op.drop_constraint(
        "model_artifacts_collection_id_fkey", "model_artifacts", type_="foreignkey"
    )
    op.drop_constraint(
        "orbit_members_orbit_id_fkey", "orbit_members", type_="foreignkey"
    )
    op.drop_constraint(
        "orbit_members_user_id_fkey", "orbit_members", type_="foreignkey"
    )
    op.drop_constraint(
        "orbit_secrets_orbit_id_fkey", "orbit_secrets", type_="foreignkey"
    )
    op.drop_constraint("orbits_organization_id_fkey", "orbits", type_="foreignkey")
    op.drop_constraint("orbits_bucket_secret_id_fkey", "orbits", type_="foreignkey")
    op.drop_constraint(
        "organization_invites_organization_id_fkey",
        "organization_invites",
        type_="foreignkey",
    )
    op.drop_constraint(
        "organization_invites_invited_by_fkey",
        "organization_invites",
        type_="foreignkey",
    )
    op.drop_constraint(
        "organization_members_organization_id_fkey",
        "organization_members",
        type_="foreignkey",
    )
    op.drop_constraint(
        "organization_members_user_id_fkey", "organization_members", type_="foreignkey"
    )
    op.drop_constraint(
        "satellite_queue_orbit_id_fkey", "satellite_queue", type_="foreignkey"
    )
    op.drop_constraint(
        "satellite_queue_satellite_id_fkey", "satellite_queue", type_="foreignkey"
    )
    op.drop_constraint("satellites_orbit_id_fkey", "satellites", type_="foreignkey")

    for table in tables_to_convert:
        for short_uuid, standard_uuid in id_mapping.items():
            connection.execute(
                sa.text(f"UPDATE {table} SET id = :new_id WHERE id = :old_id"),
                {"new_id": standard_uuid, "old_id": short_uuid},
            )

    foreign_key_mappings = {
        "bucket_secrets": ["organization_id"],
        "collections": ["orbit_id"],
        "deployments": ["orbit_id", "satellite_id", "model_id"],
        "model_artifacts": ["collection_id"],
        "orbit_members": ["user_id", "orbit_id"],
        "orbit_secrets": ["orbit_id"],
        "orbits": ["organization_id", "bucket_secret_id"],
        "organization_invites": ["organization_id", "invited_by"],
        "organization_members": ["user_id", "organization_id"],
        "satellite_queue": ["satellite_id", "orbit_id"],
        "satellites": ["orbit_id"],
    }

    for table, fk_columns in foreign_key_mappings.items():
        for column in fk_columns:
            for short_uuid, standard_uuid in id_mapping.items():
                connection.execute(
                    sa.text(
                        f"UPDATE {table} SET {column} = :new_id WHERE {column} = :old_id"
                    ),
                    {"new_id": standard_uuid, "old_id": short_uuid},
                )

    for table in tables_to_convert:
        op.alter_column(
            table,
            "id",
            existing_type=sa.VARCHAR(),
            type_=sa.UUID(),
            existing_nullable=False,
            postgresql_using="id::uuid",
        )

    op.alter_column(
        "bucket_secrets",
        "organization_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "collections",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "deployments",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "deployments",
        "satellite_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="satellite_id::uuid",
    )
    op.alter_column(
        "deployments",
        "model_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="model_id::uuid",
    )
    op.alter_column(
        "model_artifacts",
        "collection_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="collection_id::uuid",
    )
    op.alter_column(
        "orbit_members",
        "user_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "orbit_members",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "orbit_secrets",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "orbits",
        "organization_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "orbits",
        "bucket_secret_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="bucket_secret_id::uuid",
    )
    op.alter_column(
        "organization_invites",
        "organization_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "organization_invites",
        "invited_by",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="invited_by::uuid",
    )
    op.alter_column(
        "organization_members",
        "user_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "organization_members",
        "organization_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "satellite_queue",
        "satellite_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="satellite_id::uuid",
    )
    op.alter_column(
        "satellite_queue",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "satellites",
        "orbit_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )

    op.create_foreign_key(
        None,
        "bucket_secrets",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "collections", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None,
        "deployments",
        "model_artifacts",
        ["model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        None, "deployments", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "deployments", "satellites", ["satellite_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None,
        "model_artifacts",
        "collections",
        ["collection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "orbit_members", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "orbit_members", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "orbit_secrets", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "orbits", "organizations", ["organization_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None,
        "orbits",
        "bucket_secrets",
        ["bucket_secret_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "organization_invites",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "organization_invites",
        "users",
        ["invited_by"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "organization_members",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "organization_members", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "satellite_queue", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None,
        "satellite_queue",
        "satellites",
        ["satellite_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "satellites", "orbits", ["orbit_id"], ["id"], ondelete="CASCADE"
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "satellites", type_="foreignkey")
    op.drop_constraint(None, "satellite_queue", type_="foreignkey")
    op.drop_constraint(None, "satellite_queue", type_="foreignkey")
    op.drop_constraint(None, "organization_members", type_="foreignkey")
    op.drop_constraint(None, "organization_members", type_="foreignkey")
    op.drop_constraint(None, "organization_invites", type_="foreignkey")
    op.drop_constraint(None, "organization_invites", type_="foreignkey")
    op.drop_constraint(None, "orbits", type_="foreignkey")
    op.drop_constraint(None, "orbits", type_="foreignkey")
    op.drop_constraint(None, "orbit_secrets", type_="foreignkey")
    op.drop_constraint(None, "orbit_members", type_="foreignkey")
    op.drop_constraint(None, "orbit_members", type_="foreignkey")
    op.drop_constraint(None, "model_artifacts", type_="foreignkey")
    op.drop_constraint(None, "deployments", type_="foreignkey")
    op.drop_constraint(None, "deployments", type_="foreignkey")
    op.drop_constraint(None, "deployments", type_="foreignkey")
    op.drop_constraint(None, "collections", type_="foreignkey")
    op.drop_constraint(None, "bucket_secrets", type_="foreignkey")

    # Convert all columns back to VARCHAR
    op.alter_column(
        "satellites",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "satellite_queue",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "satellite_queue",
        "satellite_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "satellite_queue",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organizations",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_members",
        "organization_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_members",
        "user_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_members",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_invites",
        "invited_by",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_invites",
        "organization_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "organization_invites",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbits",
        "bucket_secret_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbits",
        "organization_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbits",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbit_secrets",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbit_secrets",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbit_members",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbit_members",
        "user_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "orbit_members",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "model_artifacts",
        "collection_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "model_artifacts",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "deployments",
        "model_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "deployments",
        "satellite_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "deployments",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "deployments",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "collections",
        "orbit_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "collections",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "bucket_secrets",
        "organization_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "bucket_secrets",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "token_black_list",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    op.alter_column(
        "stats_emails",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )
    # ### end Alembic commands ###
