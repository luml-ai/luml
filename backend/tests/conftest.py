import datetime
import random
import uuid
from dataclasses import dataclass

import asyncpg
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from dataforce_studio.models import OrganizationOrm
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.satellites import SatelliteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecret, BucketSecretCreate
from dataforce_studio.schemas.model_artifacts import (
    NDJSON,
    Collection,
    CollectionCreate,
    CollectionType,
    Manifest,
    ModelArtifactCreate,
    ModelArtifactStatus,
)
from dataforce_studio.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
)
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationInviteSimple,
    OrganizationMember,
    OrganizationMemberCreate,
    OrgRole,
    UserInvite,
)
from dataforce_studio.schemas.satellite import Satellite, SatelliteCreate
from dataforce_studio.schemas.user import AuthProvider, CreateUser, User, UserOut
from dataforce_studio.settings import config
from utils.db import migrate_db

TEST_DB_NAME = "df_studio_test"


async def _terminate_connections(conn: AsyncConnection, db_name: str) -> None:
    await conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1 AND pid <> pg_backend_pid();
        """,
        db_name,
    )


async def _create_database(admin_dsn: str, db_name: str) -> None:
    conn = await asyncpg.connect(admin_dsn)
    await _terminate_connections(conn, db_name)
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
    await conn.execute(f'CREATE DATABASE "{db_name}";')
    await conn.close()


async def _drop_database(admin_dsn: str, db_name: str) -> None:
    conn = await asyncpg.connect(admin_dsn)
    await _terminate_connections(conn, db_name)
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
    await conn.close()


@dataclass
class FixtureData:
    engine: AsyncEngine
    organization: OrganizationOrm
    orbit: OrbitDetails | None = None
    bucket_secret: BucketSecret | None = None
    collection: Collection | None = None
    satellite: Satellite | None = None
    user: User | None = None
    member: OrganizationMember | None = None
    members: list[OrganizationMember] | list[OrbitMember] | None = None
    invites: list[OrganizationInviteSimple] | list[OrganizationInvite] | None = None


@pytest_asyncio.fixture(scope="function")
async def create_database_and_apply_migrations():  # noqa: ANN201
    admin_dsn = config.POSTGRESQL_DSN.replace("+asyncpg", "").replace(
        "df_studio_test", "postgres"
    )
    test_dsn = config.POSTGRESQL_DSN

    await _create_database(admin_dsn, TEST_DB_NAME)
    await migrate_db(test_dsn)
    yield test_dsn

    await _drop_database(admin_dsn, TEST_DB_NAME)


@pytest_asyncio.fixture(scope="function")
def invite_data() -> CreateOrganizationInvite:
    return CreateOrganizationInvite(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=1,
        invited_by=1,
    )


@pytest_asyncio.fixture(scope="function")
def invite_get_data() -> OrganizationInvite:
    return OrganizationInvite(
        id=1,
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=1,
        invited_by_user=UserOut(
            id=66,
            email="robertstimothy@example.org",
            full_name="Terry Lewis",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture(scope="function")
def invite_user_get_data() -> UserInvite:
    return UserInvite(
        id=1,
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=1,
        invited_by_user=UserOut(
            id=66,
            email="robertstimothy@example.org",
            full_name="Terry Lewis",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
        organization=Organization(
            id=1,
            name="test",
            logo="https://example.com/",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        ),
    )


@pytest_asyncio.fixture(scope="function")
def invite_accept_data() -> CreateOrganizationInvite:
    return CreateOrganizationInvite(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=1,
        invited_by=1,
    )


@pytest_asyncio.fixture(scope="function")
def member_data() -> OrganizationMember:
    return OrganizationMember(
        id=987887,
        organization_id=1,
        role=OrgRole.ADMIN,
        user=UserOut(
            id=1,
            email="test@gmail.com",
            full_name="Full Name",
            disabled=False,
            photo=None,
        ),
    )


@pytest_asyncio.fixture(scope="function")
def test_user() -> CreateUser:
    return CreateUser(
        email=f"testuser_{uuid.uuid4()}@example.com",
        full_name="Test User",
        disabled=False,
        email_verified=True,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="hashed_password",
    )


@pytest_asyncio.fixture(scope="function")
def test_user_out() -> UserOut:
    return UserOut(
        id=1,
        email=f"{uuid.uuid4()}@userout.com",
        full_name="Test User",
        disabled=False,
        photo=None,
        has_api_key=False,
    )


@pytest_asyncio.fixture(scope="function")
def test_org() -> Organization:
    return Organization(
        id=1,
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture(scope="function")
def test_org_details(
    invite_get_data: OrganizationInvite, member_data: OrganizationMember
) -> OrganizationDetails:
    test_org_details_id = 8888

    return OrganizationDetails(
        id=test_org_details_id,
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        invites=[invite_get_data],
        members=[member_data],
        orbits=[
            Orbit(
                id=1,
                name="test orbit",
                organization_id=test_org_details_id,
                total_members=0,
                role=None,
                created_at=datetime.datetime.now(),
                updated_at=None,
                bucket_secret_id=1,
            )
        ],
    )


@pytest_asyncio.fixture
def manifest_example() -> Manifest:
    return Manifest(
        variant="pipeline",
        description="",
        producer_name="falcon.beastbyte.ai",
        producer_version="0.8.0",
        producer_tags=[
            "falcon.beastbyte.ai::tabular_classification:v1",
            "dataforce.studio::tabular_classification:v1",
        ],
        inputs=[
            NDJSON(
                name="sepal.length",
                content_type="NDJSON",
                dtype="Array[float32]",
                shape=["batch", 1],
                tags=["falcon.beastbyte.ai::numeric:v1"],
            ),
        ],
        outputs=[
            NDJSON(
                name="y_pred",
                content_type="NDJSON",
                dtype="Array[string]",
                shape=["batch"],
            )
        ],
        dynamic_attributes=[],
        env_vars=[],
    )


@pytest_asyncio.fixture
def test_bucket() -> BucketSecret:
    return BucketSecret(
        id=1,
        organization_id=1,
        endpoint="url",
        bucket_name="name",
        access_key="access_key",
        secret_key="secret_key",
        session_token="session_token",
        secure=True,
        region="region",
        cert_check=True,
        created_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture
def test_model_artifact(manifest_example: Manifest) -> ModelArtifactCreate:
    return ModelArtifactCreate(
        collection_id=1,
        file_name="model.dfs",
        model_name="Test Model",
        metrics={"accuracy": 0.95, "precision": 0.92},
        manifest=manifest_example,
        file_hash=str(uuid.uuid4()),
        file_index={"model": (0, 1000)},
        bucket_location="orbit/collection/model.dfs",
        size=1000,
        unique_identifier="test_uid_123",
        tags=["test", "model"],
        status=ModelArtifactStatus.PENDING_UPLOAD,
    )


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_user(
    create_database_and_apply_migrations: str, test_user: CreateUser
) -> FixtureData:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    user = await repo.create_user(test_user)

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    member_orm = await repo.get_organization_member(created_organization.id, user.id)
    member = member_orm.to_organization_member() if member_orm else None

    secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )

    return FixtureData(
        engine=engine,
        user=user,
        organization=created_organization,
        bucket_secret=secret,
        member=member,
    )


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_members(
    create_organization_with_user: FixtureData, test_user: CreateUser
) -> FixtureData:
    data = create_organization_with_user
    repo = UserRepository(data.engine)
    invites_repo = InviteRepository(data.engine)

    members = [data.member] if data.member else []
    users = [data.user]
    invites = []

    for _ in range(10):
        user_data = test_user.model_copy()
        user_data.email = f"user_{uuid.uuid4()}@gmail.com"
        user = await repo.create_user(user_data)
        users.append(user)

        member = await repo.create_organization_member(
            OrganizationMemberCreate(
                user_id=user.id,
                organization_id=data.organization.id,
                role=OrgRole.MEMBER,
            )
        )
        members.append(member)

    for _ in range(5):
        invited_by_user = random.choice(users)
        invite = await invites_repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"invited_{uuid.uuid4()}_@gmail.com",
                role=OrgRole.MEMBER,
                organization_id=data.organization.id,
                invited_by=invited_by_user.id,
            )
        )
        invites.append(invite)

    return FixtureData(
        engine=data.engine,
        organization=data.organization,
        bucket_secret=data.bucket_secret,
        user=data.user,
        member=data.member,
        members=members,
        invites=invites,
    )


@pytest_asyncio.fixture(scope="function")
async def create_orbit(
    create_database_and_apply_migrations: str, test_user: CreateUser
) -> FixtureData:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    repo = OrbitRepository(engine)

    user = await user_repo.create_user(test_user)
    created_organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    bucket_secret = await secret_repo.create_bucket_secret(
        BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
        )
    )
    created_orbit = await repo.create_orbit(
        created_organization.id,
        OrbitCreateIn(name="test orbit", bucket_secret_id=bucket_secret.id),
    )

    return FixtureData(
        engine=engine,
        organization=created_organization,
        orbit=created_orbit,
        bucket_secret=bucket_secret,
        user=user,
    )


@pytest_asyncio.fixture(scope="function")
async def create_orbit_with_members(
    create_orbit: FixtureData, test_user: CreateUser
) -> FixtureData:
    data = create_orbit
    user_repo = UserRepository(data.engine)
    repo = OrbitRepository(data.engine)
    orbit = data.orbit

    members = []

    for _ in range(10):
        user_data = test_user.model_copy()
        user_data.email = f"{uuid.uuid4()}@example.com"
        created_user = await user_repo.create_user(user_data)
        member = await repo.create_orbit_member(
            OrbitMemberCreate(
                user_id=created_user.id,
                orbit_id=orbit.id,
                role=random.choice([OrbitRole.MEMBER, OrbitRole.ADMIN]),
            )
        )
        if member:
            members.append(member)

    return FixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=orbit,
        bucket_secret=data.bucket_secret,
        members=members,
    )


@pytest_asyncio.fixture(scope="function")
async def create_collection(
    create_orbit: FixtureData, test_user: CreateUser
) -> FixtureData:
    data = create_orbit
    repo = CollectionRepository(data.engine)
    orbit = data.orbit

    collection_data = CollectionCreate(
        orbit_id=data.orbit.id,
        description="description",
        name="name",
        collection_type=CollectionType.MODEL,
        tags=["tag1", "tag2"],
    )

    collection = await repo.create_collection(collection_data)

    return FixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=orbit,
        bucket_secret=data.bucket_secret,
        collection=collection,
    )


@pytest_asyncio.fixture(scope="function")
async def create_satellite(
    create_orbit: FixtureData, test_user: CreateUser
) -> FixtureData:
    data = create_orbit
    repo = SatelliteRepository(data.engine)
    orbit = data.orbit

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, _ = await repo.create_satellite(satellite_data)

    return FixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=orbit,
        bucket_secret=data.bucket_secret,
        satellite=satellite,
    )
