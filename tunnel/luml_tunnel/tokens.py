import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from luml_tunnel.relay_api import LumlUnavailableError, RelayApi, RelayTokenRefusedError

logger = logging.getLogger(__name__)

CACHE_WINDOW_SECONDS = 60.0


class TokenKind(StrEnum):
    EXPOSE = "expose"
    VIEW = "view"


@dataclass(frozen=True)
class TunnelClaims:
    session: str
    kind: TokenKind
    user: str
    expires_at: datetime
    token_id: str


class TokenRejectedError(Exception):
    pass


class TokenCheckUnavailableError(Exception):
    """No verdict on a token can be had right now; the caller should try again."""


class TokenVerifier(Protocol):
    async def verify(self, token: str, kind: TokenKind, session: str | None = None) -> TunnelClaims:
        """Return the claims of a token that fits, or raise TokenRejectedError.

        `session` is None when the session is taken from the token itself, as when an
        agent connects to the relay's base domain. Raises TokenCheckUnavailableError
        when no verdict can be had right now.
        """
        ...

    @property
    def problem(self) -> str | None:
        """What keeps the verifier from getting verdicts, for the health check."""
        ...


@dataclass(frozen=True)
class _Verdict:
    claims: TunnelClaims | None
    fresh_until: float

    def usable(self, now: float) -> bool:
        if self.claims is None:
            return self.fresh_until > now
        return self.claims.expires_at.timestamp() > now


class LumlTokenVerifier:
    """Asks LUML about tokens and caches its verdicts, keyed by the token's hash.

    LUML answers about the token itself; whether it fits the request is checked here,
    so one verdict per token serves every request. While LUML gives no answer, cached
    claims are used past their window until the token expires on its own.
    """

    def __init__(
        self,
        api: RelayApi,
        cache_window: float = CACHE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if cache_window <= 0:
            raise ValueError("the cache window must be positive")
        self._api = api
        self._cache_window = cache_window
        self._clock = clock
        self._verdicts: dict[str, _Verdict] = {}
        self._next_cleanup = 0.0
        self._relay_token_refused = False

    @property
    def problem(self) -> str | None:
        return "LUML refuses the relay token" if self._relay_token_refused else None

    async def verify(self, token: str, kind: TokenKind, session: str | None = None) -> TunnelClaims:
        claims = await self._claims(token)
        if claims is None or claims.expires_at.timestamp() <= self._clock():
            raise TokenRejectedError("LUML does not accept the token")
        if claims.kind != kind:
            raise TokenRejectedError(f"expected a {kind} token")
        if session is not None and claims.session != session:
            raise TokenRejectedError("token is for another session")
        return claims

    async def _claims(self, token: str) -> TunnelClaims | None:
        token_id = hashlib.sha256(token.encode()).hexdigest()
        now = self._clock()
        self._forget_unusable(now)
        cached = self._verdicts.get(token_id)
        if cached is not None and cached.fresh_until > now:
            return cached.claims
        try:
            answer = await self._api.validate(token)
        except RelayTokenRefusedError as error:
            self._relay_token_refused = True
            logger.error("LUML refused the relay token when asked about a token: %s", error)
            return _stale_claims(cached, now)
        except LumlUnavailableError as error:
            logger.warning("LUML gave no verdict on a token: %s", error)
            return _stale_claims(cached, now)
        self._relay_token_refused = False
        verdict = _Verdict(None, now + self._cache_window)
        if answer is not None and answer.kind in tuple(TokenKind):
            claims = TunnelClaims(
                answer.session, TokenKind(answer.kind), answer.user, answer.expires_at, token_id
            )
            verdict = _Verdict(claims, min(verdict.fresh_until, answer.expires_at.timestamp()))
        self._verdicts[token_id] = verdict
        return verdict.claims

    def _forget_unusable(self, now: float) -> None:
        if now < self._next_cleanup:
            return
        self._next_cleanup = now + self._cache_window
        self._verdicts = {
            token_id: verdict for token_id, verdict in self._verdicts.items() if verdict.usable(now)
        }


def _stale_claims(cached: _Verdict | None, now: float) -> TunnelClaims:
    # A refusal past its window is not reused: it has no expiry of its own to bound it.
    if cached is None or cached.claims is None or not cached.usable(now):
        raise TokenCheckUnavailableError("LUML cannot be asked about the token")
    return cached.claims
