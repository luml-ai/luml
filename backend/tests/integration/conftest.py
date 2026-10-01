import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
import pytest
from luml.models import OrganizationOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.invites import InviteRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
)
from luml.schemas.bucket_secrets import S3BucketSecret, S3BucketSecretCreate
from luml.schemas.collections import (
    CollectionCreate,
    CollectionType,
)
from luml.schemas.orbit import (
    OrbitCreateIn,
    OrbitMemberCreate,
    OrbitRole,
)
from luml.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.satellite import SatelliteCreate
from luml.schemas.user import CreateUser
from luml.settings import config
from sqlalchemy import update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from utils.db import migrate_db

from tests.support.seeds import (
    TEST_ORGANIZATION_LIMITS,
    CollectionFixtureData,
    OrbitFixtureData,
    OrbitWithMembersFixtureData,
    OrganizationFixtureData,
    OrganizationWithMembersFixtureData,
    SatelliteFixtureData,
)

TEST_DB_NAME = "df_studio_test"
TEMPLATE_DB_NAME = "df_studio_test_template"


async def _terminate_connections(conn: asyncpg.Connection, db_name: str) -> None:
    await conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1 AND pid <> pg_backend_pid();
        """,
        db_name,
    )
    async with asyncio.timeout(5):
        while await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_stat_activity
                WHERE datname = $1 AND pid <> pg_backend_pid()
            );
            """,
            db_name,
        ):
            await asyncio.sleep(0.001)


async def _create_database(
    conn: asyncpg.Connection, db_name: str, *, template: str | None = None
) -> None:
    await _drop_database(conn, db_name)
    template_clause = f' TEMPLATE "{template}"' if template else ""
    await conn.execute(f'CREATE DATABASE "{db_name}"{template_clause};')


async def _drop_database(conn: asyncpg.Connection, db_name: str) -> None:
    await _terminate_connections(conn, db_name)
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')


@pytest.fixture(scope="session")
def database_template() -> Generator[tuple[str, str]]:
    test_dsn = config.POSTGRESQL_DSN
    test_url = make_url(test_dsn)
    if (
        test_url.database != TEST_DB_NAME
        or {"database", "dbname"} & test_url.query.keys()
    ):
        pytest.exit(
            f"Integration tests require POSTGRESQL_DSN to name {TEST_DB_NAME} "
            "without a database override in its query parameters.",
            returncode=pytest.ExitCode.USAGE_ERROR,
        )
    admin_dsn = test_url.set(
        drivername="postgresql", database="postgres"
    ).render_as_string(hide_password=False)
    template_dsn = test_url.set(database=TEMPLATE_DB_NAME).render_as_string(
        hide_password=False
    )

    with asyncio.Runner() as runner:
        conn = runner.run(asyncpg.connect(admin_dsn))
        try:
            runner.run(_drop_database(conn, TEST_DB_NAME))
            runner.run(_create_database(conn, TEMPLATE_DB_NAME))
            runner.run(migrate_db(template_dsn))
            yield admin_dsn, test_dsn
        finally:
            try:
                runner.run(_drop_database(conn, TEMPLATE_DB_NAME))
            finally:
                runner.run(conn.close())


@pytest.fixture
async def database_dsn(
    database_template: tuple[str, str],
) -> AsyncGenerator[str]:
    admin_dsn, test_dsn = database_template
    conn = await asyncpg.connect(admin_dsn)
    try:
        await _create_database(conn, TEST_DB_NAME, template=TEMPLATE_DB_NAME)
        yield test_dsn
    finally:
        try:
            await _drop_database(conn, TEST_DB_NAME)
        finally:
            await conn.close()


async def lift_organization_limits(engine: AsyncEngine, organization_id: UUID) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(OrganizationOrm)
            .where(OrganizationOrm.id == organization_id)
            .values(**TEST_ORGANIZATION_LIMITS)
        )
        await session.commit()


@pytest.fixture
async def engine(
    database_dsn: str,
) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(database_dsn)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def seeded_organization(
    engine: AsyncEngine, new_user: CreateUser
) -> OrganizationFixtureData:
    repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    user = await repo.create_user(new_user)

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    await lift_organization_limits(engine, created_organization.id)

    member_orm = await repo.get_organization_member(created_organization.id, user.id)
    member = member_orm.to_organization_member() if member_orm else None

    assert member is not None, (
        "Organization Member should not be None in seeded_organization fixture"
    )

    secret = await secret_repo.create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
            region="us-east-1",
        )
    )
    assert isinstance(secret, S3BucketSecret)

    return OrganizationFixtureData(
        engine=engine,
        organization=created_organization,
        user=user,
        bucket_secret=secret,
        member=member,
    )


@pytest.fixture
async def seeded_organization_with_members(
    seeded_organization: OrganizationFixtureData, new_user: CreateUser
) -> OrganizationWithMembersFixtureData:
    data = seeded_organization
    repo = UserRepository(data.engine)
    invites_repo = InviteRepository(data.engine)

    members = [data.member]
    invites = []

    for _ in range(10):
        user_data = new_user.model_copy()
        user_data.email = f"test_{uuid.uuid4()}@example.com"
        user = await repo.create_user(user_data)

        member = await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=user.id,
                organization_id=data.organization.id,
                role=OrgRole.MEMBER,
            )
        )
        if member:
            members.append(member)

    for _ in range(5):
        invite = await invites_repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"test_{uuid.uuid4()}@example.com",
                role=OrgRole.MEMBER,
                organization_id=data.organization.id,
                invited_by=data.user.id,
            )
        )
        if invite:
            invites.append(invite)

    return OrganizationWithMembersFixtureData(
        engine=data.engine,
        organization=data.organization,
        user=data.user,
        bucket_secret=data.bucket_secret,
        member=data.member,
        members=members,
        invites=invites,
    )


@pytest.fixture
async def seeded_orbit(
    seeded_organization: OrganizationFixtureData,
) -> OrbitFixtureData:
    data = seeded_organization
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="test orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert orbit is not None

    return OrbitFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
    )


@pytest.fixture
async def seeded_orbit_with_members(
    seeded_orbit: OrbitFixtureData, new_user: CreateUser
) -> OrbitWithMembersFixtureData:
    data = seeded_orbit
    user_repo = UserRepository(data.engine)
    repo = OrbitRepository(data.engine)
    orbit = data.orbit

    members = []

    for index in range(10):
        user_data = new_user.model_copy()
        user_data.email = f"test_{uuid.uuid4()}@example.com"
        created_user = await user_repo.create_user(user_data)
        member = await repo.create_orbit_member(
            OrbitMemberCreate(
                user_id=created_user.id,
                orbit_id=orbit.id,
                role=OrbitRole.ADMIN if index % 2 == 0 else OrbitRole.MEMBER,
            )
        )
        if member:
            members.append(member)

    return OrbitWithMembersFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        members=members,
    )


@pytest.fixture
async def seeded_collection(
    seeded_orbit: OrbitFixtureData,
) -> CollectionFixtureData:
    data = seeded_orbit
    repo = CollectionRepository(data.engine)

    collection_data = CollectionCreate(
        orbit_id=data.orbit.id,
        description="description",
        name="name",
        type=CollectionType.MODEL,
        tags=["tag1", "tag2"],
    )

    collection = await repo.create_collection(collection_data)

    return CollectionFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        collection=collection,
    )


@pytest.fixture
async def seeded_satellite(
    seeded_collection: CollectionFixtureData, new_artifact: ArtifactCreate
) -> SatelliteFixtureData:
    data = seeded_collection
    repo = SatelliteRepository(data.engine)
    artifact_repo = ArtifactRepository(data.engine)
    orbit, collection = data.orbit, data.collection

    artifact_data = new_artifact.model_copy()
    artifact_data.collection_id = collection.id
    artifact_data.status = ArtifactStatus.UPLOADED

    artifact = await artifact_repo.create_artifact(artifact_data)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    return SatelliteFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        model=artifact,
        satellite=satellite,
    )
