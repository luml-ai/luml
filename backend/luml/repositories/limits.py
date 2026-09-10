from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luml.infra.exceptions import NotFoundError, OrganizationLimitReachedError
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    OrbitOrm,
    OrganizationMemberOrm,
    OrganizationOrm,
    SatelliteOrm,
    UserOrm,
)


class OrganizationResource(StrEnum):
    ARTIFACTS = "artifacts"
    ORBITS = "orbits"
    SATELLITES = "satellites"
    MEMBERS = "members"


ORGANIZATION_MEMBERSHIP_LIMIT = 5

MEMBERSHIP_LIMIT_MESSAGE = (
    "You’ve reached the limit of organizations you can join or create"
)

_LIMIT_MESSAGES = {
    OrganizationResource.ARTIFACTS: "Organization reached maximum number of artifacts",
    OrganizationResource.ORBITS: "Organization reached maximum number of orbits",
    OrganizationResource.SATELLITES: (
        "Organization reached maximum number of satellites"
    ),
    OrganizationResource.MEMBERS: "Organization reached maximum number of users",
}


def _usage_query(
    resource: OrganizationResource, organization_id: UUID
) -> Select[tuple[int]]:
    if resource is OrganizationResource.ARTIFACTS:
        return (
            select(func.count(ArtifactOrm.id))
            .join(CollectionOrm, ArtifactOrm.collection_id == CollectionOrm.id)
            .join(OrbitOrm, CollectionOrm.orbit_id == OrbitOrm.id)
            .where(OrbitOrm.organization_id == organization_id)
        )
    if resource is OrganizationResource.ORBITS:
        return select(func.count(OrbitOrm.id)).where(
            OrbitOrm.organization_id == organization_id
        )
    if resource is OrganizationResource.SATELLITES:
        return (
            select(func.count(SatelliteOrm.id))
            .join(OrbitOrm, SatelliteOrm.orbit_id == OrbitOrm.id)
            .where(OrbitOrm.organization_id == organization_id)
        )
    return select(func.count(OrganizationMemberOrm.id)).where(
        OrganizationMemberOrm.organization_id == organization_id
    )


async def reserve_organization_slot(
    session: AsyncSession, organization_id: UUID, resource: OrganizationResource
) -> None:
    """Lock the organization row and fail if ``resource`` is at its limit."""
    limit_column = getattr(OrganizationOrm, f"{resource.value}_limit")
    limit = await session.scalar(
        select(limit_column)
        .where(OrganizationOrm.id == organization_id)
        .with_for_update()
    )
    if limit is None:
        raise NotFoundError("Organization not found")
    used = await session.scalar(_usage_query(resource, organization_id)) or 0
    if used >= limit:
        raise OrganizationLimitReachedError(_LIMIT_MESSAGES[resource])


async def reserve_user_membership_slot(
    session: AsyncSession, user_id: UUID, limit: int
) -> None:
    """Lock the user row and fail if the user is already in ``limit`` organizations."""
    locked = await session.scalar(
        select(UserOrm.id).where(UserOrm.id == user_id).with_for_update()
    )
    if locked is None:
        raise NotFoundError("User not found")
    used = (
        await session.scalar(
            select(func.count(OrganizationMemberOrm.id)).where(
                OrganizationMemberOrm.user_id == user_id
            )
        )
        or 0
    )
    if used >= limit:
        raise OrganizationLimitReachedError(MEMBERSHIP_LIMIT_MESSAGE)
