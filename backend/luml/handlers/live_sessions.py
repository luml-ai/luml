from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    LiveSessionEndedError,
    LiveSessionsNotConfiguredError,
    NotFoundError,
)
from luml.infra.live_session_tokens import (
    TunnelTokenKind,
    TunnelTokenSigner,
    load_signing_key,
)
from luml.repositories.live_sessions import LiveSessionRepository
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
from luml.settings import Settings, config

LAUNCH_PATH = "/.luml-tunnel/launch"
_HTTP_SCHEMES = {"ws": "http", "wss": "https", "http": "http", "https": "https"}


@dataclass(frozen=True)
class _Relay:
    relay_id: str
    base_domain: str
    agent_url: str
    signer: TunnelTokenSigner
    expose_lifetime: timedelta
    view_lifetime: timedelta

    def public_url(self, session_id: str) -> str:
        # Session hostnames are served like the address agents connect to,
        # with the same scheme and port.
        agent_address = urlsplit(self.agent_url)
        scheme = _HTTP_SCHEMES[agent_address.scheme]
        port = f":{agent_address.port}" if agent_address.port else ""
        return f"{scheme}://{session_id}.{self.base_domain}{port}"


def _signer_from(settings: Settings) -> TunnelTokenSigner | None:
    if not settings.LIVE_SESSION_SIGNING_KEY:
        return None
    return TunnelTokenSigner(load_signing_key(settings.LIVE_SESSION_SIGNING_KEY))


def _relay_from(settings: Settings, signer: TunnelTokenSigner | None) -> _Relay | None:
    relay_id = settings.LIVE_SESSION_RELAY_ID
    base_domain = settings.LIVE_SESSION_RELAY_BASE_DOMAIN
    agent_url = settings.LIVE_SESSION_RELAY_AGENT_URL
    if not (signer and relay_id and base_domain and agent_url):
        return None
    if urlsplit(agent_url).scheme not in _HTTP_SCHEMES:
        raise ValueError("LIVE_SESSION_RELAY_AGENT_URL must be a ws(s) address")
    return _Relay(
        relay_id=relay_id,
        base_domain=base_domain,
        agent_url=agent_url,
        signer=signer,
        expose_lifetime=timedelta(
            seconds=settings.LIVE_SESSION_EXPOSE_TOKEN_LIFETIME_SECONDS
        ),
        view_lifetime=timedelta(
            seconds=settings.LIVE_SESSION_VIEW_TOKEN_LIFETIME_SECONDS
        ),
    )


class LiveSessionHandler:
    __repo = LiveSessionRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(self, settings: Settings = config) -> None:
        self._signer = _signer_from(settings)
        self._relay = _relay_from(settings, self._signer)
        self._app_url = settings.APP_EMAIL_URL.rstrip("/")

    def public_keys(self) -> dict[str, list[dict[str, str]]]:
        return {"keys": [self._signer.public_jwk] if self._signer else []}

    def _require_relay(self) -> _Relay:
        if self._relay is None:
            raise LiveSessionsNotConfiguredError()
        return self._relay

    async def _authorize(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        action: Action,
    ) -> _Relay:
        relay = self._require_relay()
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.LIVE_SESSION, action, orbit_id
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
        relay = await self._authorize(user_id, organization_id, orbit_id, Action.CREATE)
        live_session = await self.__repo.create_live_session(
            LiveSessionCreate(
                orbit_id=orbit_id,
                user_id=user_id,
                name=data.name,
                relay_id=relay.relay_id,
            )
        )
        token, expires_at = relay.signer.sign(
            TunnelTokenKind.EXPOSE,
            live_session.relay_id,
            live_session.id,
            str(user_id),
            relay.expose_lifetime,
        )
        return LiveSessionStartOut(
            id=live_session.id,
            public_url=relay.public_url(live_session.id),
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
        relay = await self._authorize(user_id, organization_id, orbit_id, Action.UPDATE)
        await self._get_visible_session(user_id, orbit_id, session_id)
        live_session = await self.__repo.record_heartbeat(session_id, data.connected)
        if live_session is None:
            raise NotFoundError("Live session not found")
        if live_session.status == LiveSessionStatus.ENDED:
            return LiveSessionHeartbeatOut(status=live_session.status)

        # Renewing at half the lifetime leaves several heartbeats to deliver
        # the new token before the current one expires.
        remaining = data.token_expires_at - datetime.now(UTC)
        if remaining > relay.expose_lifetime / 2:
            return LiveSessionHeartbeatOut(status=live_session.status)
        token, expires_at = relay.signer.sign(
            TunnelTokenKind.EXPOSE,
            live_session.relay_id,
            live_session.id,
            str(user_id),
            relay.expose_lifetime,
        )
        return LiveSessionHeartbeatOut(
            status=live_session.status,
            expose_token=token,
            token_expires_at=expires_at,
        )

    async def issue_view_token(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, session_id: str
    ) -> LiveSessionViewTokenOut:
        relay = await self._authorize(user_id, organization_id, orbit_id, Action.READ)
        live_session = await self._get_visible_session(user_id, orbit_id, session_id)
        if live_session.status == LiveSessionStatus.ENDED:
            raise LiveSessionEndedError()
        token, expires_at = relay.signer.sign(
            TunnelTokenKind.VIEW,
            live_session.relay_id,
            live_session.id,
            str(user_id),
            relay.view_lifetime,
        )
        launch_url = (
            f"{relay.public_url(live_session.id)}{LAUNCH_PATH}"
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
