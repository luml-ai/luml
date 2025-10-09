"""Change id type

Revision ID: 018
Revises: 017
Create Date: 2025-10-03 22:41:37.498397

"""
# ruff: noqa: E501, W291

import contextlib
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
import uuid6
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid7_from_datetime(dt: datetime | None = None) -> uuid6.UUID:
    if dt is None:
        dt = datetime.now(UTC)

    timestamp_ms = int(dt.timestamp() * 1000)
    uuid_int = (timestamp_ms & 0xFFFFFFFFFFFF) << 80
    uuid_int |= secrets.randbits(76)

    return uuid6.UUID(int=uuid_int, version=7)


def upgrade() -> None:
    op.add_column("bucket_secrets", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("collections", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("deployments", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("model_artifacts", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("orbit_members", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("orbit_secrets", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("orbits", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column(
        "organization_invites", sa.Column("old_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "organization_members", sa.Column("old_id", sa.Integer(), nullable=True)
    )
    op.add_column("organizations", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("satellite_queue", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("satellites", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("stats_emails", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("token_black_list", sa.Column("old_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("old_id", sa.Integer(), nullable=True))

    op.execute("UPDATE bucket_secrets SET old_id = id")
    op.execute("UPDATE collections SET old_id = id")
    op.execute("UPDATE deployments SET old_id = id")
    op.execute("UPDATE model_artifacts SET old_id = id")
    op.execute("UPDATE orbit_members SET old_id = id")
    op.execute("UPDATE orbit_secrets SET old_id = id")
    op.execute("UPDATE orbits SET old_id = id")
    op.execute("UPDATE organization_invites SET old_id = id")
    op.execute("UPDATE organization_members SET old_id = id")
    op.execute("UPDATE organizations SET old_id = id")
    op.execute("UPDATE satellite_queue SET old_id = id")
    op.execute("UPDATE satellites SET old_id = id")
    op.execute("UPDATE stats_emails SET old_id = id")
    op.execute("UPDATE token_black_list SET old_id = id")
    op.execute("UPDATE users SET old_id = id")

    connection = op.get_bind()

    tables_with_fks = [
        "deployments",
        "satellites",
        "satellite_queue",
        "organization_members",
        "organization_invites",
        "orbits",
        "orbit_secrets",
        "orbit_members",
        "model_artifacts",
        "collections",
        "bucket_secrets",
    ]

    for table in tables_with_fks:
        result = connection.execute(
            sa.text(f"""
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = '{table}'::regclass 
            AND contype = 'f'
        """)
        )
        constraints = result.fetchall()

        for constraint in constraints:
            constraint_name = constraint[0]
            with contextlib.suppress(Exception):
                connection.execute(
                    sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint_name}")
                )

    tables_with_ids = [
        "organizations",
        "users",
        "bucket_secrets",
        "orbits",
        "deployments",
        "satellites",
        "collections",
        "model_artifacts",
        "orbit_members",
        "orbit_secrets",
        "organization_invites",
        "organization_members",
        "satellite_queue",
        "stats_emails",
        "token_black_list",
    ]

    for table in tables_with_ids:
        connection.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT"))
        op.alter_column(
            table,
            "id",
            existing_type=sa.INTEGER(),
            type_=sa.Text(),
            existing_nullable=False,
        )

    tables = [
        "organizations",
        "users",
        "bucket_secrets",
        "orbits",
        "deployments",
        "satellites",
        "collections",
        "model_artifacts",
        "orbit_members",
        "orbit_secrets",
        "organization_invites",
        "organization_members",
        "satellite_queue",
        "stats_emails",
        "token_black_list",
    ]

    for table in tables:
        if table == "token_black_list":
            result = connection.execute(sa.text(f"SELECT old_id FROM {table}"))
            records = result.fetchall()

            for record in records:
                new_uuid7 = uuid7_from_datetime()
                connection.execute(
                    sa.text(f"UPDATE {table} SET id = :new_id WHERE old_id = :old_id"),
                    {"new_id": str(new_uuid7), "old_id": record[0]},
                )
        else:
            result = connection.execute(
                sa.text(f"SELECT old_id, created_at FROM {table}")
            )
            records = result.fetchall()

            for record in records:
                new_uuid7 = uuid7_from_datetime(record[1])
                connection.execute(
                    sa.text(f"UPDATE {table} SET id = :new_id WHERE old_id = :old_id"),
                    {"new_id": str(new_uuid7), "old_id": record[0]},
                )

    op.alter_column(
        "bucket_secrets",
        "organization_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE bucket_secrets 
        SET organization_id = organizations.id 
        FROM organizations 
        WHERE bucket_secrets.organization_id::integer = organizations.old_id
    """)
    )
    op.alter_column(
        "bucket_secrets",
        "organization_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "collections",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE collections 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE collections.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "collections",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "deployments",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE deployments 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE deployments.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "deployments",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "deployments",
        "satellite_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE deployments 
        SET satellite_id = satellites.id 
        FROM satellites 
        WHERE deployments.satellite_id::integer = satellites.old_id
    """)
    )
    op.alter_column(
        "deployments",
        "satellite_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="satellite_id::uuid",
    )
    op.alter_column(
        "deployments",
        "model_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE deployments 
        SET model_id = model_artifacts.id 
        FROM model_artifacts 
        WHERE deployments.model_id::integer = model_artifacts.old_id
    """)
    )
    op.alter_column(
        "deployments",
        "model_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="model_id::uuid",
    )
    op.alter_column(
        "model_artifacts",
        "collection_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE model_artifacts 
        SET collection_id = collections.id 
        FROM collections 
        WHERE model_artifacts.collection_id::integer = collections.old_id
    """)
    )
    op.alter_column(
        "model_artifacts",
        "collection_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="collection_id::uuid",
    )
    op.alter_column(
        "orbit_members",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE orbit_members 
        SET user_id = users.id 
        FROM users 
        WHERE orbit_members.user_id::integer = users.old_id
    """)
    )
    op.alter_column(
        "orbit_members",
        "user_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "orbit_members",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE orbit_members 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE orbit_members.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "orbit_members",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "orbit_secrets",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE orbit_secrets 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE orbit_secrets.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "orbit_secrets",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "orbits",
        "organization_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE orbits 
        SET organization_id = organizations.id 
        FROM organizations 
        WHERE orbits.organization_id::integer = organizations.old_id
    """)
    )
    op.alter_column(
        "orbits",
        "organization_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "orbits",
        "bucket_secret_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE orbits 
        SET bucket_secret_id = bucket_secrets.id 
        FROM bucket_secrets 
        WHERE orbits.bucket_secret_id::integer = bucket_secrets.old_id
    """)
    )
    op.alter_column(
        "orbits",
        "bucket_secret_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="bucket_secret_id::uuid",
    )
    op.alter_column(
        "organization_invites",
        "organization_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE organization_invites 
        SET organization_id = organizations.id 
        FROM organizations 
        WHERE organization_invites.organization_id::integer = organizations.old_id
    """)
    )
    op.alter_column(
        "organization_invites",
        "organization_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "organization_invites",
        "invited_by",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE organization_invites 
        SET invited_by = users.id 
        FROM users 
        WHERE organization_invites.invited_by::integer = users.old_id
    """)
    )
    op.alter_column(
        "organization_invites",
        "invited_by",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="invited_by::uuid",
    )
    op.alter_column(
        "organization_members",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE organization_members 
        SET user_id = users.id 
        FROM users 
        WHERE organization_members.user_id::integer = users.old_id
    """)
    )
    op.alter_column(
        "organization_members",
        "user_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "organization_members",
        "organization_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE organization_members 
        SET organization_id = organizations.id 
        FROM organizations 
        WHERE organization_members.organization_id::integer = organizations.old_id
    """)
    )
    op.alter_column(
        "organization_members",
        "organization_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "satellite_queue",
        "satellite_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE satellite_queue 
        SET satellite_id = satellites.id 
        FROM satellites 
        WHERE satellite_queue.satellite_id::integer = satellites.old_id
    """)
    )
    op.alter_column(
        "satellite_queue",
        "satellite_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="satellite_id::uuid",
    )
    op.alter_column(
        "satellite_queue",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE satellite_queue 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE satellite_queue.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "satellite_queue",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )
    op.alter_column(
        "satellites",
        "orbit_id",
        existing_type=sa.INTEGER(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    connection.execute(
        sa.text("""
        UPDATE satellites 
        SET orbit_id = orbits.id 
        FROM orbits 
        WHERE satellites.orbit_id::integer = orbits.old_id
    """)
    )
    op.alter_column(
        "satellites",
        "orbit_id",
        existing_type=sa.Text(),
        type_=sa.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="orbit_id::uuid",
    )

    for table in tables_with_ids:
        op.alter_column(
            table,
            "id",
            existing_type=sa.Text(),
            type_=sa.UUID(as_uuid=True),
            existing_nullable=False,
            postgresql_using="id::uuid",
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


def downgrade() -> None:
    connection = op.get_bind()

    tables_with_fks = [
        "satellites",
        "satellite_queue",
        "organization_members",
        "organization_invites",
        "orbits",
        "orbit_secrets",
        "orbit_members",
        "deployments",
        "model_artifacts",
        "collections",
        "bucket_secrets",
    ]

    for table in tables_with_fks:
        result = connection.execute(
            sa.text(f"""
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = '{table}'::regclass 
            AND contype = 'f'
        """)
        )
        constraints = result.fetchall()

        for constraint in constraints:
            constraint_name = constraint[0]
            connection.execute(
                sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint_name}")
            )

    tables = [
        "users",
        "token_black_list",
        "stats_emails",
        "deployments",
        "satellites",
        "satellite_queue",
        "organizations",
        "organization_members",
        "organization_invites",
        "orbits",
        "orbit_secrets",
        "orbit_members",
        "model_artifacts",
        "collections",
        "bucket_secrets",
    ]

    foreign_key_updates = [
        ("bucket_secrets", "organization_id", "organizations"),
        ("collections", "orbit_id", "orbits"),
        ("deployments", "orbit_id", "orbits"),
        ("deployments", "satellite_id", "satellites"),
        ("deployments", "model_id", "model_artifacts"),
        ("model_artifacts", "collection_id", "collections"),
        ("orbit_members", "user_id", "users"),
        ("orbit_members", "orbit_id", "orbits"),
        ("orbit_secrets", "orbit_id", "orbits"),
        ("orbits", "organization_id", "organizations"),
        ("orbits", "bucket_secret_id", "bucket_secrets"),
        ("organization_invites", "organization_id", "organizations"),
        ("organization_invites", "invited_by", "users"),
        ("organization_members", "user_id", "users"),
        ("organization_members", "organization_id", "organizations"),
        ("satellite_queue", "satellite_id", "satellites"),
        ("satellite_queue", "orbit_id", "orbits"),
        ("satellites", "orbit_id", "orbits"),
    ]

    for table, fk_column, ref_table in foreign_key_updates:
        connection.execute(
            sa.text(f"""
            UPDATE {table} 
            SET {fk_column} = {ref_table}.old_id::text 
            FROM {ref_table} 
            WHERE {table}.{fk_column}::uuid = {ref_table}.id
        """)
        )

        connection.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {fk_column} TYPE INTEGER USING {fk_column}::integer"
            )
        )

    for table in tables:
        connection.execute(sa.text(f"UPDATE {table} SET id = old_id"))
        connection.execute(
            sa.text(f"ALTER TABLE {table} ALTER COLUMN id TYPE INTEGER USING old_id")
        )

    op.drop_column("bucket_secrets", "old_id")
    op.drop_column("collections", "old_id")
    op.drop_column("deployments", "old_id")
    op.drop_column("model_artifacts", "old_id")
    op.drop_column("orbit_members", "old_id")
    op.drop_column("orbit_secrets", "old_id")
    op.drop_column("orbits", "old_id")
    op.drop_column("organization_invites", "old_id")
    op.drop_column("organization_members", "old_id")
    op.drop_column("organizations", "old_id")
    op.drop_column("satellite_queue", "old_id")
    op.drop_column("satellites", "old_id")
    op.drop_column("stats_emails", "old_id")
    op.drop_column("token_black_list", "old_id")
    op.drop_column("users", "old_id")

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
