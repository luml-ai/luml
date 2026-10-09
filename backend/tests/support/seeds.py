from dataclasses import dataclass

from luml.models import OrganizationOrm
from luml.schemas.artifacts import Artifact
from luml.schemas.bucket_secrets import S3BucketSecret
from luml.schemas.collections import Collection
from luml.schemas.orbit import (
    OrbitDetails,
    OrbitMember,
)
from luml.schemas.organization import (
    OrganizationInviteSimple,
    OrganizationMember,
)
from luml.schemas.satellite import Satellite
from luml.schemas.user import User
from sqlalchemy.ext.asyncio import AsyncEngine

TEST_ORGANIZATION_LIMITS = {
    "members_limit": 1000,
    "orbits_limit": 1000,
    "satellites_limit": 1000,
    "artifacts_limit": 1000,
}


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
    model: Artifact
    satellite: Satellite
