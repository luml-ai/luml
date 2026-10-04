import logging
from datetime import UTC, datetime
from uuid import UUID

from luml.infra.db import engine
from luml.infra.exceptions import NotFoundError
from luml.repositories.live_session_tokens import LiveSessionTokenRepository
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.relays import RelayRepository
from luml.schemas.live_session import (
    LIVE_SESSION_GRANT_LIFETIME,
    LiveSession,
    LiveSessionStatus,
    LiveSessionToken,
    TunnelTokenKind,
)
from luml.schemas.relay import (
    RelayDescription,
    RelayReportIn,
    TunnelGrantVerdict,
    TunnelTokenValidateIn,
    TunnelTokenVerdict,
)
from luml.settings import Settings, config

logger = logging.getLogger(__name__)


def _inactive_reason(
    token: LiveSessionToken, live_session: LiveSession, relay_id: UUID
) -> str | None:
    if token.expires_at <= datetime.now(UTC):
        return "expired"
    if live_session.relay_id != relay_id:
        return "its session is not on this relay"
    if live_session.status == LiveSessionStatus.ENDED:
        return "its session has ended"
    return None


def _log_inactive(relay_id: UUID, credential: str, reason: str) -> None:
    logger.info("Relay %s: %s is inactive, %s", relay_id, credential, reason)


class RelayWorkerHandler:
    """What a relay asks LUML; every answer is scoped to the calling relay.

    An inactive verdict never says why, so a public relay cannot be used to
    probe which sessions exist; the reason goes to the log only.
    """

    __relay_repo = RelayRepository(engine)
    __session_repo = LiveSessionRepository(engine)
    __token_repo = LiveSessionTokenRepository(engine)

    def __init__(self, settings: Settings = config) -> None:
        self._app_origins = [
            origin.strip() for origin in settings.CORS_ORIGINS.split(",")
        ]
        self._app_url = settings.APP_EMAIL_URL.rstrip("/")

    async def describe(self, relay_id: UUID) -> RelayDescription:
        relay = await self.__relay_repo.get_relay(relay_id)
        if relay is None:
            raise NotFoundError("Relay not found")
        return RelayDescription(
            id=relay.id,
            label=relay.label,
            base_domain=relay.base_domain,
            agent_url=relay.agent_url,
            status=relay.status,
            app_origins=self._app_origins,
            app_url=self._app_url,
        )

    async def validate_token(
        self, relay_id: UUID, data: TunnelTokenValidateIn
    ) -> TunnelTokenVerdict:
        found = await self.__token_repo.get_token_with_session(data.token)
        if found is None:
            _log_inactive(relay_id, "token", "unknown")
            return TunnelTokenVerdict(active=False)
        token, live_session = found
        reason = _inactive_reason(token, live_session, relay_id)
        if token.launched_at is not None:
            # From its launch on, the row is a grant reachable only by its id.
            reason = "already launched"
        elif data.launch and token.kind != TunnelTokenKind.VIEW:
            reason = "only view tokens launch"
        if reason is None and data.launch:
            launched = await self.__token_repo.launch_view_token(
                token.id, datetime.now(UTC) + LIVE_SESSION_GRANT_LIFETIME
            )
            if launched is None:
                reason = "launched concurrently"
            else:
                token = launched
        if reason is not None:
            _log_inactive(relay_id, "token", reason)
            return TunnelTokenVerdict(active=False)

        if token.kind == TunnelTokenKind.VIEW:
            await self.__session_repo.record_viewer_activity(token.session_id)
        return TunnelTokenVerdict(
            active=True,
            kind=token.kind,
            session_id=token.session_id,
            user_id=token.user_id,
            expires_at=token.expires_at,
            grant_id=token.id if data.launch else None,
            destination=token.destination if data.launch else None,
        )

    async def check_grant(self, relay_id: UUID, grant_id: UUID) -> TunnelGrantVerdict:
        found = await self.__token_repo.get_grant_with_session(grant_id)
        if found is None:
            _log_inactive(relay_id, "grant", "unknown")
            return TunnelGrantVerdict(active=False)
        grant, live_session = found
        reason = _inactive_reason(grant, live_session, relay_id)
        if grant.launched_at is None:
            reason = "not launched"
        if reason is not None:
            _log_inactive(relay_id, "grant", reason)
            return TunnelGrantVerdict(active=False)

        await self.__session_repo.record_viewer_activity(grant.session_id)
        return TunnelGrantVerdict(
            active=True,
            session_id=grant.session_id,
            user_id=grant.user_id,
            expires_at=grant.expires_at,
        )

    async def report(self, relay_id: UUID, report: RelayReportIn) -> None:
        await self.__relay_repo.record_report(
            relay_id, report.connected_agents, report.capabilities
        )
