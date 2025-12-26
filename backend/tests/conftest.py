import datetime
import random
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid7

import asyncpg  # type: ignore[import-untyped]
import pytest_asyncio
from luml.models import OrganizationOrm
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.invites import InviteRepository
from luml.repositories.model_artifacts import ModelArtifactRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.users import UserRepository
from luml.schemas.bucket_secrets import S3BucketSecret, S3BucketSecretCreate
from luml.schemas.model_artifacts import (
    NDJSON,
    Collection,
    CollectionCreate,
    CollectionType,
    Manifest,
    ModelArtifact,
    ModelArtifactCreate,
    ModelArtifactStatus,
)
from luml.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
)
from luml.schemas.organization import (
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
from luml.schemas.satellite import Satellite, SatelliteCreate
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    User,
    UserOut,
)
from luml.settings import config
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from utils.db import migrate_db

TEST_DB_NAME = "luml_studio_test"
TEST_PASSWORD = "test_password"


async def _terminate_connections(conn: AsyncConnection, db_name: str) -> None:
    await conn.execute(  # type: ignore[call-overload]
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
class BaseFixtureData:
    engine: AsyncEngine
    organization: OrganizationOrm


@dataclass
class OrganizationFixtureData(BaseFixtureData):
    user: User
    bucket_secret: S3BucketSecret
    member: OrganizationMember


@dataclass
class OrganizationWithMembersFixtureData(OrganizationFixtureData):
    members: list[OrganizationMember]
    invites: list[OrganizationInviteSimple]


@dataclass
class OrbitFixtureData(BaseFixtureData):
    orbit: OrbitDetails
    bucket_secret: S3BucketSecret
    user: User


@dataclass
class OrbitWithMembersFixtureData(OrbitFixtureData):
    members: list[OrbitMember]


@dataclass
class CollectionFixtureData(OrbitFixtureData):
    collection: Collection


@dataclass
class SatelliteFixtureData(OrbitFixtureData):
    model: ModelArtifact
    satellite: Satellite


@pytest_asyncio.fixture(scope="function")
async def create_database_and_apply_migrations() -> AsyncGenerator[str]:  # noqa: ANN201
    admin_dsn = config.POSTGRESQL_DSN.replace("+asyncpg", "").replace(
        "df_studio_test", "postgres"
    )
    test_dsn = config.POSTGRESQL_DSN

    await _create_database(admin_dsn, TEST_DB_NAME)
    await migrate_db(test_dsn)
    yield test_dsn

    await _drop_database(admin_dsn, TEST_DB_NAME)


@pytest_asyncio.fixture(scope="function")
async def invite_data() -> AsyncGenerator[CreateOrganizationInvite]:
    yield CreateOrganizationInvite(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=uuid7(),
        invited_by=uuid7(),
    )


@pytest_asyncio.fixture(scope="function")
async def invite_get_data() -> AsyncGenerator[OrganizationInvite]:
    yield OrganizationInvite(
        id=uuid7(),
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=uuid7(),
        invited_by_user=UserOut(
            id=uuid7(),
            email="robertstimothy@example.org",
            full_name="Terry Lewis",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture(scope="function")
async def invite_user_get_data() -> AsyncGenerator[UserInvite]:
    yield UserInvite(
        id=uuid7(),
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=uuid7(),
        invited_by_user=UserOut(
            id=uuid7(),
            email="robertstimothy@example.org",
            full_name="Terry Lewis",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
        organization=Organization(
            id=uuid7(),
            name="test",
            logo=None,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        ),
    )


@pytest_asyncio.fixture(scope="function")
async def invite_accept_data() -> AsyncGenerator[CreateOrganizationInvite]:
    yield CreateOrganizationInvite(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=uuid7(),
        invited_by=uuid7(),
    )


@pytest_asyncio.fixture(scope="function")
async def member_data() -> AsyncGenerator[OrganizationMember]:
    yield OrganizationMember(
        id=uuid7(),
        organization_id=uuid7(),
        role=OrgRole.OWNER,
        user=UserOut(
            id=uuid7(),
            email="test@example.com",
            full_name="Full Name",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture(scope="function")
async def test_user_create() -> AsyncGenerator[CreateUser]:
    yield CreateUser(
        email=f"test_{uuid.uuid4()}@example.com",
        full_name="Test User",
        disabled=None,
        email_verified=False,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$GZPWq5NMO1CsJrHq+EpiTA$E2QWHVvlRyMcPb4231Bh9pBhnjjENgeqYdb1M7lsIXs",
    )


@pytest_asyncio.fixture(scope="function")
async def test_user_create_in(
    test_user_create: CreateUser,
) -> AsyncGenerator[CreateUserIn]:
    user = test_user_create.model_copy()
    yield CreateUserIn(
        email=user.email,
        full_name=user.full_name,
        photo=user.photo,
        password=TEST_PASSWORD,
    )


@pytest_asyncio.fixture(scope="function")
async def test_user(test_user_create: CreateUser) -> AsyncGenerator[User]:
    user = test_user_create.model_copy()
    yield User(
        id=uuid7(),
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        email_verified=True,
        auth_method=user.auth_method,
        photo=user.photo,
        hashed_password=user.hashed_password,
    )


@pytest_asyncio.fixture(scope="function")
async def test_user_out(test_user: User) -> AsyncGenerator[UserOut]:
    user = test_user.model_copy()
    yield UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        photo=user.photo,
        has_api_key=False,
    )


@pytest_asyncio.fixture(scope="function")
async def test_org() -> AsyncGenerator[Organization]:
    yield Organization(
        id=uuid7(),
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest_asyncio.fixture(scope="function")
async def test_org_details(
    invite_get_data: OrganizationInvite, member_data: OrganizationMember
) -> AsyncGenerator[OrganizationDetails]:
    test_org_details_id = uuid7()

    yield OrganizationDetails(
        id=test_org_details_id,
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        invites=[invite_get_data],
        members=[member_data],
        orbits=[
            Orbit(
                id=uuid7(),
                name="test orbit",
                organization_id=test_org_details_id,
                total_members=0,
                role=None,
                created_at=datetime.datetime.now(),
                updated_at=None,
                bucket_secret_id=uuid7(),
            )
        ],
    )


@pytest_asyncio.fixture
async def manifest_example() -> AsyncGenerator[Manifest]:
    yield Manifest(
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
async def test_bucket() -> AsyncGenerator[S3BucketSecret]:
    yield S3BucketSecret(
        id=uuid7(),
        organization_id=uuid7(),
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
async def test_model_artifact(
    manifest_example: Manifest,
) -> AsyncGenerator[ModelArtifactCreate]:
    yield ModelArtifactCreate(
        collection_id=uuid7(),
        file_name="model.luml",
        model_name="Test Model",
        metrics={"accuracy": 0.95, "precision": 0.92},
        manifest=manifest_example,
        file_hash=str(uuid.uuid4()),
        file_index={"model": (0, 1000)},
        bucket_location="orbit/collection/model.luml",
        size=1000,
        unique_identifier="test_uid_123",
        tags=["test", "model"],
        status=ModelArtifactStatus.PENDING_UPLOAD,
        created_by_user="User FullName",
    )


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_user(
    create_database_and_apply_migrations: str, test_user_create: CreateUser
) -> OrganizationFixtureData:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    user = await repo.create_user(test_user_create)

    assert user is not None, (
        "User should not be None in create_organization_with_user fixture"
    )

    created_organization = await repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )

    assert created_organization is not None, (
        "Organization should not be None in create_organization_with_user fixture"
    )

    member_orm = await repo.get_organization_member(created_organization.id, user.id)
    member = member_orm.to_organization_member() if member_orm else None

    assert member is not None, (
        "Organization Member should not be None in "
        "create_organization_with_user fixture"
    )

    secret = await secret_repo.create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=created_organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
            region="us-east-1",
        )
    )
    assert secret is not None, (
        "BucketSecret should not be None in create_organization_with_user fixture"
    )

    return OrganizationFixtureData(
        engine=engine,
        organization=created_organization,
        user=user,
        bucket_secret=secret,
        member=member,
    )


@pytest_asyncio.fixture(scope="function")
async def create_organization_with_members(
    create_organization_with_user: OrganizationFixtureData, test_user_create: CreateUser
) -> OrganizationWithMembersFixtureData:
    data = create_organization_with_user
    repo = UserRepository(data.engine)
    invites_repo = InviteRepository(data.engine)

    members = [data.member] if data.member else []
    users = [data.user]
    invites = []

    for _ in range(10):
        user_data = test_user_create.model_copy()
        user_data.email = f"test_{uuid.uuid4()}@example.com"
        user = await repo.create_user(user_data)
        users.append(user)

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
        invited_by_user = random.choice(users)
        invite = await invites_repo.create_organization_invite(
            CreateOrganizationInvite(
                email=f"test_{uuid.uuid4()}@example.com",
                role=OrgRole.MEMBER,
                organization_id=data.organization.id,
                invited_by=invited_by_user.id,
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


@pytest_asyncio.fixture(scope="function")
async def create_orbit(
    create_database_and_apply_migrations: str, test_user_create: CreateUser
) -> OrbitFixtureData:
    engine = create_async_engine(create_database_and_apply_migrations)
    user_repo = UserRepository(engine)
    secret_repo = BucketSecretRepository(engine)
    repo = OrbitRepository(engine)

    user = await user_repo.create_user(test_user_create)
    assert user is not None, "User should not be None in create_orbit fixture"

    organization = await user_repo.create_organization(
        user.id, OrganizationCreateIn(name="test org")
    )
    assert organization is not None, (
        "Organization should not be None in create_orbit fixture"
    )

    bucket_secret = await secret_repo.create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test-bucket",
            region="us-east-1",
        )
    )
    assert bucket_secret is not None, (
        "BucketSecret should not be None in create_orbit fixture"
    )

    orbit = await repo.create_orbit(
        organization.id,
        OrbitCreateIn(name="test orbit", bucket_secret_id=bucket_secret.id),
    )
    assert orbit is not None, "Orbit should not be None in create_orbit fixture"

    return OrbitFixtureData(
        engine=engine,
        organization=organization,
        orbit=orbit,
        bucket_secret=bucket_secret,
        user=user,
    )


@pytest_asyncio.fixture(scope="function")
async def create_orbit_with_members(
    create_orbit: OrbitFixtureData, test_user_create: CreateUser
) -> OrbitWithMembersFixtureData:
    data = create_orbit
    user_repo = UserRepository(data.engine)
    repo = OrbitRepository(data.engine)
    orbit = data.orbit

    members = []

    for _ in range(10):
        user_data = test_user_create.model_copy()
        user_data.email = f"test_{uuid.uuid4()}@example.com"
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

    return OrbitWithMembersFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        members=members,
    )


@pytest_asyncio.fixture(scope="function")
async def create_collection(
    create_orbit: OrbitFixtureData, test_user_create: CreateUser
) -> CollectionFixtureData:
    data = create_orbit
    repo = CollectionRepository(data.engine)

    collection_data = CollectionCreate(
        orbit_id=data.orbit.id,
        description="description",
        name="name",
        collection_type=CollectionType.MODEL,
        tags=["tag1", "tag2"],
    )

    collection = await repo.create_collection(collection_data)
    assert collection is not None, (
        "Collection should not be None in create_collection fixture"
    )

    return CollectionFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        collection=collection,
    )


@pytest_asyncio.fixture(scope="function")
async def create_satellite(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> SatelliteFixtureData:
    data = create_collection
    repo = SatelliteRepository(data.engine)
    model_artifact_repo = ModelArtifactRepository(data.engine)
    orbit, collection = data.orbit, data.collection

    assert orbit is not None, "Orbit should not be None in create_satellite fixture"
    assert collection is not None, (
        "Collection should not be None in create_satellite fixture"
    )

    model_data = test_model_artifact.model_copy()
    model_data.collection_id = collection.id

    model = await model_artifact_repo.create_model_artifact(model_data)
    assert model is not None, (
        "ModelArtifact should not be None in create_satellite fixture"
    )

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    assert satellite is not None, (
        "Satellite should not be None in create_satellite fixture"
    )

    return SatelliteFixtureData(
        engine=data.engine,
        organization=data.organization,
        orbit=data.orbit,
        bucket_secret=data.bucket_secret,
        user=data.user,
        model=model,
        satellite=satellite,
    )
