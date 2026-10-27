import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from luml.models import LiveSessionOrm, LiveSessionTokenOrm, OrganizationOrm
from luml.repositories.limits import OrganizationResource
from luml.repositories.live_session_tokens import LiveSessionTokenRepository
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionTokenCreate,
    LiveSessionVisibility,
    SessionTokenKind,
)
from luml.schemas.relay import Relay, RelayCreate
from luml.schemas.user import CreateUser
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.seeds import OrbitFixtureData

OWN = OrganizationResource.OWN_RELAY_SESSIONS
MANAGED = OrganizationResource.MANAGED_RELAY_SESSIONS


async def create_relay(
    engine: AsyncEngine, organization_id: uuid.UUID | None, label: str = "lab"
) -> Relay:
    unique = uuid.uuid4().hex[:12]
    return await RelayRepository(engine).create_relay(
        RelayCreate(
            label=label,
            base_domain=f"{unique}.sessions.example",
            agent_url="wss://sessions.example/connect",
            organization_id=organization_id,
            token_hash=unique,
        )
    )


async def start_session(
    data: OrbitFixtureData,
    user_id: uuid.UUID | None = None,
    label: str | None = "run",
    relay: Relay | None = None,
    orbit_id: uuid.UUID | None = None,
) -> LiveSession:
    relay = relay or await create_relay(data.engine, data.organization.id)
    return await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=orbit_id or data.orbit.id,
            user_id=user_id or data.user.id,
            label=label,
            visibility=LiveSessionVisibility.OWNER,
            relay_id=relay.id,
        ),
        data.organization.id,
        OWN if relay.organization_id else MANAGED,
    )


async def set_limits(
    engine: AsyncEngine, organization_id: uuid.UUID, **limits: int
) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(OrganizationOrm)
            .where(OrganizationOrm.id == organization_id)
            .values(**limits)
        )
        await session.commit()


async def set_fields(engine: AsyncEngine, session_id: str, **values: Any) -> None:  # noqa: ANN401
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionOrm)
            .where(LiveSessionOrm.id == session_id)
            .values(**values)
        )
        await session.commit()


async def create_other_user(engine: AsyncEngine, template: CreateUser) -> uuid.UUID:
    user_data = template.model_copy()
    user_data.email = f"other_{uuid.uuid4()}@example.com"
    user = await UserRepository(engine).create_user(user_data)
    return user.id


async def unviewed_for(
    engine: AsyncEngine, session_id: str, idle_for: timedelta
) -> None:
    now = datetime.now(UTC)
    await set_fields(
        engine,
        session_id,
        started_at=now - idle_for,
        last_heartbeat_at=now - timedelta(seconds=10),
        connected=True,
    )


async def count_tokens(engine: AsyncEngine, session_id: str) -> int:
    async with AsyncSession(engine) as session:
        count = await session.scalar(
            select(func.count(LiveSessionTokenOrm.id)).where(
                LiveSessionTokenOrm.session_id == session_id
            )
        )
        return count or 0


async def issue_expose_token(engine: AsyncEngine, session: LiveSession) -> None:
    await LiveSessionTokenRepository(engine).issue_token(
        LiveSessionTokenCreate(
            kind=SessionTokenKind.EXPOSE,
            session_id=session.id,
            user_id=session.user_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
