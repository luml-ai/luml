import base64
import hashlib
import hmac
import json
import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# `__Host-` makes browsers refuse the cookie unless it is Secure, host-only and on `/`,
# so a page on another session's hostname cannot plant it.
COOKIE_NAME = "__Host-luml-relay"
IDLE_LIFETIME_SECONDS = 30 * 60
MAX_LIFETIME_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class ViewerCookie:
    session: str
    user: str
    grant: str
    issued_at: float
    expires_at: float
    value: str


class ViewerCookies:
    """Signs the relay's cookie, bound to one session, one user and the grant at LUML.

    A cookie ends after `idle_lifetime` without requests and `max_lifetime` after launch,
    which the relay decides from the cookie alone.
    """

    def __init__(
        self,
        secret: bytes | None = None,
        clock: Callable[[], float] = time.time,
        idle_lifetime: float = IDLE_LIFETIME_SECONDS,
        max_lifetime: float = MAX_LIFETIME_SECONDS,
    ) -> None:
        if secret == b"":
            raise ValueError("the cookie secret must not be empty")
        self._secret = secret or secrets.token_bytes(32)
        self._clock = clock
        self._idle_lifetime = idle_lifetime
        self._max_lifetime = max_lifetime

    def issue(self, session: str, user: str, grant: str) -> ViewerCookie:
        return self._signed(session, user, grant, self._clock())

    def renew(self, value: str, session: str) -> ViewerCookie | None:
        """Return a renewed cookie for a valid value of this session, otherwise None."""
        payload = self._verified_payload(value)
        if payload is None or payload.get("session") != session:
            return None
        try:
            user, grant = payload["user"], payload["grant"]
            issued_at, expires_at = payload["iat"], payload["exp"]
        except KeyError:
            return None
        if (
            not isinstance(user, str)
            or not isinstance(grant, str)
            or not all(isinstance(moment, int | float) for moment in (issued_at, expires_at))
        ):
            return None
        if self._clock() >= min(expires_at, issued_at + self._max_lifetime):
            return None
        return self._signed(session, user, grant, issued_at)

    def set_cookie_header(self, cookie: ViewerCookie) -> str:
        max_age = max(0, math.ceil(cookie.expires_at - self._clock()))
        # SameSite=None with Partitioned lets browsers keep it inside the LUML app's frame.
        return (
            f"{COOKIE_NAME}={cookie.value}; Max-Age={max_age}; Path=/; "
            "Secure; HttpOnly; SameSite=None; Partitioned"
        )

    def _signed(self, session: str, user: str, grant: str, issued_at: float) -> ViewerCookie:
        now = self._clock()
        expires_at = min(now + self._idle_lifetime, issued_at + self._max_lifetime)
        payload = {
            "session": session,
            "user": user,
            "grant": grant,
            "iat": issued_at,
            "exp": expires_at,
        }
        encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        value = f"{encoded}.{self._signature(encoded)}"
        return ViewerCookie(session, user, grant, issued_at, expires_at, value)

    def _verified_payload(self, value: str) -> dict[str, Any] | None:
        encoded, _, signature = value.partition(".")
        if not value.isascii() or not hmac.compare_digest(signature, self._signature(encoded)):
            return None
        try:
            payload = json.loads(_decode(encoded))
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def _signature(self, encoded: str) -> str:
        return _encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
