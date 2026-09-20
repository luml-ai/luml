import base64
import hashlib
import hmac
import json
import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE_NAME = "monitoring_session"
DEFAULT_SESSION_TTL_SECONDS = 30 * 60
DEFAULT_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class MonitoringSession:
    session_id: str
    deployment_id: UUID
    scope: str
    issued_at: float
    expires_at: float
    hard_deadline: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at or now >= self.hard_deadline


class MonitoringSessionStore:
    def __init__(
        self,
        secret: str | bytes | None = None,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
        max_age_seconds: int = DEFAULT_SESSION_MAX_AGE_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be greater than zero")
        secret_bytes = secret.encode() if isinstance(secret, str) else secret
        if secret_bytes == b"":
            raise ValueError("session secret must not be empty")
        self._secret = secret_bytes or secrets.token_bytes(32)
        self._ttl_seconds = ttl_seconds
        self._max_age_seconds = max_age_seconds
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def create(self, deployment_id: UUID, scope: str) -> MonitoringSession:
        now = self._clock()
        session = MonitoringSession(
            session_id="",
            deployment_id=deployment_id,
            scope=scope,
            issued_at=now,
            expires_at=min(now + self._ttl_seconds, now + self._max_age_seconds),
            hard_deadline=now + self._max_age_seconds,
        )
        return self._with_token(session)

    def get(self, session_id: str) -> MonitoringSession | None:
        session = self._decode(session_id)
        if session is None:
            return None
        now = self._clock()
        if session.is_expired(now):
            return None
        renewed = replace(
            session,
            session_id="",
            expires_at=min(now + self._ttl_seconds, session.hard_deadline),
        )
        return self._with_token(renewed)

    def cookie_max_age(self, session: MonitoringSession) -> int:
        return max(0, math.ceil(min(self._ttl_seconds, session.hard_deadline - self._clock())))

    def _with_token(self, session: MonitoringSession) -> MonitoringSession:
        payload = {
            "deployment": str(session.deployment_id),
            "scope": session.scope,
            "issued_at": session.issued_at,
            "expiry": session.expires_at,
            "hard_deadline": session.hard_deadline,
        }
        encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        signature = _encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())
        return replace(session, session_id=f"{encoded}.{signature}")

    def _decode(self, token: str) -> MonitoringSession | None:
        try:
            encoded, signature = token.split(".", maxsplit=1)
            expected = _encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                return None
            payload: Any = json.loads(_decode(encoded))
            if not isinstance(payload, dict):
                return None
            issued_at = float(payload["issued_at"])
            expires_at = float(payload["expiry"])
            hard_deadline = float(payload["hard_deadline"])
            scope = payload["scope"]
            if not isinstance(scope, str) or not issued_at <= expires_at <= hard_deadline:
                return None
            return MonitoringSession(
                session_id=token,
                deployment_id=UUID(str(payload["deployment"])),
                scope=scope,
                issued_at=issued_at,
                expires_at=expires_at,
                hard_deadline=hard_deadline,
            )
        except KeyError, TypeError, ValueError, json.JSONDecodeError:
            return None


def set_monitoring_cookie(
    response: Response,
    store: MonitoringSessionStore,
    session: MonitoringSession,
    *,
    secure: bool,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=store.cookie_max_age(session),
        httponly=True,
        secure=secure,
        samesite="none",
        path="/monitoring",
    )


def require_monitoring_write(request: Request, response: Response) -> MonitoringSession:
    return require_monitoring_session(request, response)


def require_monitoring_session(request: Request, response: Response) -> MonitoringSession:
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
    set_monitoring_cookie(
        response,
        store,
        session,
        secure=bool(request.app.state.monitoring_cookie_secure),
    )
    return session


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
