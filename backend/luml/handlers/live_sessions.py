from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import status

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    LiveSessionEndedError,
    LiveSessionsNotConfiguredError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.infra.live_session_tokens import (
    TunnelTokenKind,
    TunnelTokenSigner,
    load_signing_key,
)
from luml.repositories.limits import OrganizationResource
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionHeartbeatIn,
    LiveSessionHeartbeatOut,
    LiveSessionStartIn,
    LiveSessionStartOut,
    LiveSessionStatus,
    LiveSessionViewTokenOut,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import Relay, RelayKind, RelayStatus
from luml.settings import Settings, config

LAUNCH_PATH = "/.luml-tunnel/launch"
_HTTP_SCHEMES = {"ws": "http", "wss": "https"}
_SESSION_LIMITS = {
    RelayKind.MANAGED: OrganizationResource.MANAGED_RELAY_SESSIONS,
    RelayKind.OWN: OrganizationResource.OWN_RELAY_SESSIONS,
}


def _public_url(relay: Relay, session_id: str) -> str:
    # Session hostnames are served like the address agents connect to,
    # with the same scheme and port.
    agent_address = urlsplit(relay.agent_url)
    scheme = _HTTP_SCHEMES[agent_address.scheme]
    port = f":{agent_address.port}" if agent_address.port else ""
    return f"{scheme}://{session_id}.{relay.base_domain}{port}"


def _signer_from(settings: Settings) -> TunnelTokenSigner | None:
    if not settings.LIVE_SESSION_SIGNING_KEY:
        return None
    return TunnelTokenSigner(load_signing_key(settings.LIVE_SESSION_SIGNING_KEY))


class LiveSessionHandler:
    __repo = LiveSessionRepository(engine)
    __orbit_repo = OrbitRepository(engine)
    __relay_repo = RelayRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(self, settings: Settings = config) -> None:
        self._signer = _signer_from(settings)
        self._expose_lifetime = timedelta(
            seconds=settings.LIVE_SESSION_EXPOSE_TOKEN_LIFETIME_SECONDS
        )
        self._view_lifetime = timedelta(
            seconds=settings.LIVE_SESSION_VIEW_TOKEN_LIFETIME_SECONDS
        )
        self._app_url = settings.APP_EMAIL_URL.rstrip("/")

    def public_keys(self) -> dict[str, list[dict[str, str]]]:
        return {"keys": [self._signer.public_jwk] if self._signer else []}

    async def _authorize(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        action: Action,
    ) -> TunnelTokenSigner:
        if self._signer is None:
            raise LiveSessionsNotConfiguredError()
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.LIVE_SESSION, action, orbit_id
        )
        return self._signer

    async def _relay_for_new_session(
        self, organization_id: UUID, orbit_id: UUID
    ) -> Relay:
        orbit = await self.__orbit_repo.get_orbit_simple(orbit_id, organization_id)
        if orbit is None:
            raise OrbitNotFoundError()
        relay = (
            await self.__relay_repo.get_relay(orbit.relay_id)
            if orbit.relay_id
            else None
        )
        if relay is None:
            raise ApplicationError(
                "The orbit has no relay; assign a relay in orbit settings",
                status.HTTP_409_CONFLICT,
            )
        if relay.status == RelayStatus.DRAINING:
            raise ApplicationError(
                f"Relay '{relay.label}' is draining and takes no new sessions",
                status.HTTP_409_CONFLICT,
            )
        return relay

    @staticmethod
    def _is_visible_to(live_session: LiveSession, user_id: UUID) -> bool:
        return live_session.user_id == user_id

    async def _get_visible_session(
        self, user_id: UUID, orbit_id: UUID, session_id: str
    ) -> LiveSession:
        # Sessions of other users answer "not found", so their existence stays hidden.
        live_session = await self.__repo.get_live_session(session_id)
        if (
            live_session is None
            or live_session.orbit_id != orbit_id
            or not self._is_visible_to(live_session, user_id)
        ):
            raise NotFoundError("Live session not found")
        return live_session

    def _app_url_for(
        self, organization_id: UUID, orbit_id: UUID, session_id: str
    ) -> str:
        return (
            f"{self._app_url}/organization/{organization_id}"
            f"/orbit/{orbit_id}/flow/{session_id}"
        )

    async def start_session(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: LiveSessionStartIn,
    ) -> LiveSessionStartOut:
        signer = await self._authorize(
            user_id, organization_id, orbit_id, Action.CREATE
        )
        relay = await self._relay_for_new_session(organization_id, orbit_id)
        limit = _SESSION_LIMITS[relay.kind]
        await self.__repo.check_session_slot(organization_id, limit)
        live_session = await self.__repo.create_live_session(
            LiveSessionCreate(
                orbit_id=orbit_id,
                user_id=user_id,
                name=data.name,
                relay_id=relay.id,
            ),
            organization_id,
            limit,
        )
        token, expires_at = signer.sign(
            TunnelTokenKind.EXPOSE,
            str(relay.id),
            live_session.id,
            str(user_id),
            self._expose_lifetime,
        )
        return LiveSessionStartOut(
            id=live_session.id,
            public_url=_public_url(relay, live_session.id),
            app_url=self._app_url_for(organization_id, orbit_id, live_session.id),
            agent_url=relay.agent_url,
            expose_token=token,
            token_expires_at=expires_at,
        )

    async def list_sessions(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[LiveSession]:
        await self._authorize(user_id, organization_id, orbit_id, Action.LIST)
        sessions = await self.__repo.list_live_sessions(orbit_id, user_id)
        return [s for s in sessions if self._is_visible_to(s, user_id)]

    async def get_session(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, session_id: str
    ) -> LiveSession:
        await self._authorize(user_id, organization_id, orbit_id, Action.READ)
        return await self._get_visible_session(user_id, orbit_id, session_id)

    async def record_heartbeat(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        session_id: str,
        data: LiveSessionHeartbeatIn,
    ) -> LiveSessionHeartbeatOut:
        signer = await self._authorize(
            user_id, organization_id, orbit_id, Action.UPDATE
        )
        await self._get_visible_session(user_id, orbit_id, session_id)
        live_session = await self.__repo.record_heartbeat(session_id, data.connected)
        if live_session is None:
            raise NotFoundError("Live session not found")
        # A session loses its relay only once it has ended.
        if (
            live_session.status == LiveSessionStatus.ENDED
            or live_session.relay_id is None
        ):
            return LiveSessionHeartbeatOut(status=LiveSessionStatus.ENDED)

        # Renewing at half the lifetime leaves several heartbeats to deliver
        # the new token before the current one expires.
        remaining = data.token_expires_at - datetime.now(UTC)
        if remaining > self._expose_lifetime / 2:
            return LiveSessionHeartbeatOut(status=live_session.status)
        token, expires_at = signer.sign(
            TunnelTokenKind.EXPOSE,
            str(live_session.relay_id),
            live_session.id,
            str(user_id),
            self._expose_lifetime,
        )
        return LiveSessionHeartbeatOut(
            status=live_session.status,
            expose_token=token,
            token_expires_at=expires_at,
        )

    async def issue_view_token(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, session_id: str
    ) -> LiveSessionViewTokenOut:
        signer = await self._authorize(user_id, organization_id, orbit_id, Action.READ)
        live_session = await self._get_visible_session(user_id, orbit_id, session_id)
        relay = (
            await self.__relay_repo.get_relay(live_session.relay_id)
            if live_session.relay_id
            else None
        )
        if live_session.status == LiveSessionStatus.ENDED or relay is None:
            raise LiveSessionEndedError()
        token, expires_at = signer.sign(
            TunnelTokenKind.VIEW,
            str(relay.id),
            live_session.id,
            str(user_id),
            self._view_lifetime,
        )
        launch_url = (
            f"{_public_url(relay, live_session.id)}{LAUNCH_PATH}"
            f"?{urlencode({'token': token})}"
        )
        return LiveSessionViewTokenOut(
            token=token, launch_url=launch_url, expires_at=expires_at
        )

    async def end_session(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, session_id: str
    ) -> LiveSession:
        await self._authorize(user_id, organization_id, orbit_id, Action.DELETE)
        await self._get_visible_session(user_id, orbit_id, session_id)
        live_session = await self.__repo.end_live_session(session_id)
        if live_session is None:
            raise NotFoundError("Live session not found")
        return live_session
