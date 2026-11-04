import uuid
from datetime import UTC, datetime, timedelta

from luml.handlers.relays import RelayHandler
from luml.models import LiveSessionOrm
from luml.repositories.limits import OrganizationResource
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionVisibility,
)
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.organization import OrganizationMemberCreate, OrgRole
from luml.schemas.relay import Relay, RelayCreate
from luml.schemas.user import CreateUser
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.seeds import OrganizationFixtureData

TOKEN_HASHER = RelayHandler()


async def create_relay_with_token(
    engine: AsyncEngine,
    base_domain: str,
    token: str,
    organization_id: uuid.UUID | None = None,
    label: str = "lab",
) -> Relay:
    return await RelayRepository(engine).create_relay(
        RelayCreate(
            label=label,
            base_domain=base_domain,
            agent_url="wss://relay.example/connect",
            organization_id=organization_id,
            token_hash=TOKEN_HASHER.hash_token(token),
        )
    )


async def authenticated_relay_id(engine: AsyncEngine, token: str) -> uuid.UUID | None:
    relay = await RelayRepository(engine).get_relay_by_token_hash(
        TOKEN_HASHER.hash_token(token)
    )
    return relay.id if relay else None


async def add_organization_user(
    data: OrganizationFixtureData, new_user: CreateUser, role: OrgRole
) -> uuid.UUID:
    repo = UserRepository(data.engine)
    user = await repo.create_user(
        new_user.model_copy(update={"email": f"{uuid.uuid4()}@example.com"})
    )
    await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id, organization_id=data.organization.id, role=role
        )
    )
    return user.id


async def create_orbit_on_relay(
    data: OrganizationFixtureData, relay: Relay
) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(
            name=f"orbit {uuid.uuid4().hex[:6]}",
            bucket_secret_id=data.bucket_secret.id,
            relay_id=relay.id,
        ),
    )
    assert orbit is not None
    return orbit


async def start_session_on_relay(
    data: OrganizationFixtureData, orbit: OrbitDetails, relay: Relay
) -> LiveSession:
    return await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=orbit.id,
            user_id=data.user.id,
            label="run",
            visibility=LiveSessionVisibility.OWNER,
            relay_id=relay.id,
        ),
        data.organization.id,
        OrganizationResource.OWN_RELAY_SESSIONS,
    )


async def silence_session(
    engine: AsyncEngine, session_id: str, silent_for: timedelta
) -> None:
    since = datetime.now(UTC) - silent_for
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionOrm)
            .where(LiveSessionOrm.id == session_id)
            .values(started_at=since, last_heartbeat_at=since, connected=True)
        )
        await session.commit()
