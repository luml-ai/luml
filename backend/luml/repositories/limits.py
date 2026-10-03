from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luml.infra.exceptions import NotFoundError, OrganizationLimitReachedError
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    LiveSessionOrm,
    OrbitOrm,
    OrganizationMemberOrm,
    OrganizationOrm,
    RelayOrm,
    SatelliteOrm,
    UserOrm,
)
from luml.models.live_session import live_session_unended


class OrganizationResource(StrEnum):
    ARTIFACTS = "artifacts"
    ORBITS = "orbits"
    SATELLITES = "satellites"
    MEMBERS = "members"
    MANAGED_RELAY_SESSIONS = "managed_relay_sessions"
    OWN_RELAY_SESSIONS = "own_relay_sessions"


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
    OrganizationResource.MANAGED_RELAY_SESSIONS: (
        "Organization reached maximum number of sessions on managed relays"
    ),
    OrganizationResource.OWN_RELAY_SESSIONS: (
        "Organization reached maximum number of sessions on its own relays"
    ),
}


def _relay_sessions_usage_query(
    organization_id: UUID, managed: bool, excluded_session_id: str | None
) -> Select[tuple[int]]:
    relay_owner = RelayOrm.organization_id
    query = (
        select(func.count(LiveSessionOrm.id))
        .join(OrbitOrm, LiveSessionOrm.orbit_id == OrbitOrm.id)
        .join(RelayOrm, LiveSessionOrm.relay_id == RelayOrm.id)
        .where(
            OrbitOrm.organization_id == organization_id,
            relay_owner.is_(None) if managed else relay_owner.is_not(None),
            live_session_unended(datetime.now(UTC)),
        )
    )
    if excluded_session_id is not None:
        query = query.where(LiveSessionOrm.id != excluded_session_id)
    return query


def _usage_query(
    resource: OrganizationResource,
    organization_id: UUID,
    excluded_session_id: str | None = None,
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
    if resource is OrganizationResource.MANAGED_RELAY_SESSIONS:
        return _relay_sessions_usage_query(
            organization_id, managed=True, excluded_session_id=excluded_session_id
        )
    if resource is OrganizationResource.OWN_RELAY_SESSIONS:
        return _relay_sessions_usage_query(
            organization_id, managed=False, excluded_session_id=excluded_session_id
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
    session: AsyncSession,
    organization_id: UUID,
    resource: OrganizationResource,
    lock: bool = True,
    excluded_session_id: str | None = None,
) -> None:
    """Refuse when the organization has used up its limit for the resource.

    With `lock`, the organization row stays locked until the caller's
    transaction ends, so concurrent inserts are counted one after another.
    `excluded_session_id` names a live session counted as free because the
    new one replaces it.
    """
    limit_column = getattr(OrganizationOrm, f"{resource.value}_limit")
    query = select(limit_column).where(OrganizationOrm.id == organization_id)
    limit = await session.scalar(query.with_for_update() if lock else query)
    if limit is None:
        raise NotFoundError("Organization not found")
    usage = _usage_query(resource, organization_id, excluded_session_id)
    used = await session.scalar(usage) or 0
    if used >= limit:
        raise OrganizationLimitReachedError(_LIMIT_MESSAGES[resource])


async def reserve_user_membership_slot(
    session: AsyncSession, user_id: UUID, limit: int
) -> None:
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
