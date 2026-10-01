import datetime
import uuid
from uuid import uuid7

import pytest
from luml.schemas.artifacts import (
    NDJSON,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.bucket_secrets import S3BucketSecret
from luml.schemas.orbit import Orbit
from luml.schemas.organization import (
    CreateOrganizationInvite,
    Organization,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationMember,
    OrgRole,
    UserInvite,
)
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    CurrentUserOut,
    User,
    UserOut,
)

TEST_PASSWORD = "test_password"


@pytest.fixture
def new_invite() -> CreateOrganizationInvite:
    return CreateOrganizationInvite(
        email="test@example.com",
        role=OrgRole.MEMBER,
        organization_id=uuid7(),
        invited_by=uuid7(),
    )


@pytest.fixture
def invite() -> OrganizationInvite:
    return OrganizationInvite(
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


@pytest.fixture
def user_invite() -> UserInvite:
    return UserInvite(
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


@pytest.fixture
def organization_member() -> OrganizationMember:
    return OrganizationMember(
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


@pytest.fixture
def new_user() -> CreateUser:
    return CreateUser(
        email=f"test_{uuid.uuid4()}@example.com",
        full_name="Test User",
        disabled=None,
        email_verified=False,
        auth_method=AuthProvider.EMAIL,
        photo=None,
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$GZPWq5NMO1CsJrHq+EpiTA$E2QWHVvlRyMcPb4231Bh9pBhnjjENgeqYdb1M7lsIXs",
    )


@pytest.fixture
def new_user_in(
    new_user: CreateUser,
) -> CreateUserIn:
    user = new_user.model_copy()
    return CreateUserIn(
        email=user.email,
        full_name=user.full_name,
        photo=user.photo,
        password=TEST_PASSWORD,
    )


@pytest.fixture
def user(new_user: CreateUser) -> User:
    user = new_user.model_copy()
    return User(
        id=uuid7(),
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        email_verified=True,
        auth_method=user.auth_method,
        photo=user.photo,
        hashed_password=user.hashed_password,
    )


@pytest.fixture
def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        photo=user.photo,
        has_api_key=False,
    )


@pytest.fixture
def current_user_out(user: User) -> CurrentUserOut:
    return CurrentUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        photo=user.photo,
        has_api_key=False,
        auth_method=user.auth_method,
    )


@pytest.fixture
def organization() -> Organization:
    return Organization(
        id=uuid7(),
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def organization_details(
    invite: OrganizationInvite, organization_member: OrganizationMember
) -> OrganizationDetails:
    test_org_details_id = uuid7()

    return OrganizationDetails(
        id=test_org_details_id,
        name="Test organization",
        logo=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        invites=[invite],
        members=[organization_member],
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


@pytest.fixture
def manifest() -> Manifest:
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


@pytest.fixture
def bucket_secret() -> S3BucketSecret:
    return S3BucketSecret(
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


@pytest.fixture
def new_artifact(
    manifest: Manifest,
) -> ArtifactCreate:
    return ArtifactCreate(
        collection_id=uuid7(),
        file_name="model.luml",
        name="Test Model",
        extra_values={"accuracy": 0.95, "precision": 0.92},
        manifest=manifest,
        file_hash=str(uuid.uuid4()),
        file_index={"model": (0, 1000)},
        bucket_location="orbit/collection/model.luml",
        size=1000,
        unique_identifier="test_uid_123",
        tags=["test", "model"],
        status=ArtifactStatus.PENDING_UPLOAD,
        created_by_user="User FullName",
        type=ArtifactType.MODEL,
    )


@pytest.fixture
def test_user_create(new_user: CreateUser) -> CreateUser:
    return new_user


@pytest.fixture
def test_user_create_in(new_user_in: CreateUserIn) -> CreateUserIn:
    return new_user_in


@pytest.fixture
def test_user(user: User) -> User:
    return user


@pytest.fixture
def test_user_out(user_out: UserOut) -> UserOut:
    return user_out


@pytest.fixture
def test_current_user_out(current_user_out: CurrentUserOut) -> CurrentUserOut:
    return current_user_out


@pytest.fixture
def test_org(organization: Organization) -> Organization:
    return organization


@pytest.fixture
def test_org_details(organization_details: OrganizationDetails) -> OrganizationDetails:
    return organization_details


@pytest.fixture
def test_bucket(bucket_secret: S3BucketSecret) -> S3BucketSecret:
    return bucket_secret


@pytest.fixture
def test_artifact(new_artifact: ArtifactCreate) -> ArtifactCreate:
    return new_artifact


@pytest.fixture
def manifest_example(manifest: Manifest) -> Manifest:
    return manifest


@pytest.fixture
def invite_data(new_invite: CreateOrganizationInvite) -> CreateOrganizationInvite:
    return new_invite


@pytest.fixture
def invite_accept_data(
    new_invite: CreateOrganizationInvite,
) -> CreateOrganizationInvite:
    return new_invite


@pytest.fixture
def invite_get_data(invite: OrganizationInvite) -> OrganizationInvite:
    return invite


@pytest.fixture
def invite_user_get_data(user_invite: UserInvite) -> UserInvite:
    return user_invite


@pytest.fixture
def member_data(organization_member: OrganizationMember) -> OrganizationMember:
    return organization_member
