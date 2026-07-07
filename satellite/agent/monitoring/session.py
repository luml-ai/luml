import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, Request, status

SESSION_COOKIE_NAME = "monitoring_session"
DEFAULT_SESSION_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class MonitoringSession:
    session_id: str
    deployment_id: UUID
    scope: str
    expires_at: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class MonitoringSessionStore:
    """In-memory dashboard-session store.

    The Agent runs as a single process, so sessions live in memory. Each session is
    scoped to exactly one ``deployment_id``; the cookie only carries the opaque id.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, MonitoringSession] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def create(self, deployment_id: UUID, scope: str) -> MonitoringSession:
        now = self._clock()
        self._purge_expired(now)
        session = MonitoringSession(
            session_id=secrets.token_urlsafe(32),
            deployment_id=deployment_id,
            scope=scope,
            expires_at=now + self._ttl_seconds,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> MonitoringSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired(self._clock()):
            del self._sessions[session_id]
            return None
        return session

    def _purge_expired(self, now: float) -> None:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired(now)]
        for sid in expired:
            del self._sessions[sid]


def require_monitoring_session(request: Request) -> MonitoringSession:
    """Resolve the active dashboard session, deriving ``deployment_id`` from the cookie.

    Every monitoring query depends on this so its deployment scope comes from the session
    and never from a client-supplied parameter. Returns ``401`` when the session cookie is
    missing or the session has expired.
    """
    store: MonitoringSessionStore = request.app.state.monitoring_sessions
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Monitoring session required",
        )
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Monitoring session expired",
        )
    return session
