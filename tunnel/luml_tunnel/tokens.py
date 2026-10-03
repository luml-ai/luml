import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from luml_tunnel.relay_api import (
    ActiveToken,
    LumlUnavailableError,
    RelayApi,
    RelayTokenRefusedError,
)

logger = logging.getLogger(__name__)

CACHE_WINDOW_SECONDS = 60.0
MAX_CACHE_ENTRIES = 100_000

# Token keys are hex digests, so this prefix keeps grants apart from them.
_GRANT_KEY_PREFIX = "grant:"


class TokenKind(StrEnum):
    EXPOSE = "expose"
    VIEW = "view"


@dataclass(frozen=True)
class TunnelClaims:
    session: str
    kind: TokenKind
    user: str
    expires_at: datetime


@dataclass(frozen=True)
class Launch:
    claims: TunnelClaims
    grant: str
    destination: str | None


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

    async def launch(self, token: str, session: str) -> Launch:
        """Consume a `view` token of the session and return the grant it became.

        A token is launched once; a launch is never answered from a cache. Raises as
        `verify` does.
        """
        ...

    async def check_grant(self, grant: str, session: str) -> TunnelClaims:
        """Return the claims of an active grant of the session; raises as `verify` does."""
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
    """Asks LUML about tokens and grants and caches its verdicts.

    Verdicts on tokens are keyed by the token's hash, verdicts on grants by the grant.
    LUML answers about the token itself; whether it fits the request is checked here,
    so one verdict per token serves every request. While LUML gives no answer, cached
    claims are used past their window until the token expires on its own. Beyond
    `max_entries` verdicts, the oldest are evicted.
    """

    def __init__(
        self,
        api: RelayApi,
        cache_window: float = CACHE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.time,
        max_entries: int = MAX_CACHE_ENTRIES,
    ) -> None:
        if cache_window <= 0:
            raise ValueError("the cache window must be positive")
        if max_entries <= 0:
            raise ValueError("the cache must hold at least one entry")
        self._api = api
        self._cache_window = cache_window
        self._max_entries = max_entries
        self._clock = clock
        self._verdicts: dict[str, _Verdict] = {}
        self._next_cleanup = 0.0
        self._relay_token_refused = False

    @property
    def problem(self) -> str | None:
        return "LUML refuses the relay token" if self._relay_token_refused else None

    async def verify(self, token: str, kind: TokenKind, session: str | None = None) -> TunnelClaims:
        claims = await self._cached(_token_key(token), lambda: self._ask_about_token(token))
        return self._fitting(claims, kind, session)

    async def check_grant(self, grant: str, session: str) -> TunnelClaims:
        claims = await self._cached(_GRANT_KEY_PREFIX + grant, lambda: self._ask_about_grant(grant))
        return self._fitting(claims, TokenKind.VIEW, session)

    async def launch(self, token: str, session: str) -> Launch:
        try:
            answer = await self._api.validate(token, launch=True)
        except LumlUnavailableError as error:
            self._note_no_answer(error)
            raise TokenCheckUnavailableError("LUML cannot be asked about the launch") from error
        self._relay_token_refused = False
        if answer is None or answer.grant is None:
            raise TokenRejectedError("LUML does not accept the launch token")
        # The token is consumed, so cached claims must not let it in by the header.
        self._verdicts.pop(_token_key(token), None)
        claims = self._fitting(_claims_of(answer), TokenKind.VIEW, session)
        return Launch(claims, answer.grant, answer.destination)

    def _fitting(
        self, claims: TunnelClaims | None, kind: TokenKind, session: str | None
    ) -> TunnelClaims:
        if claims is None or claims.expires_at.timestamp() <= self._clock():
            raise TokenRejectedError("LUML does not accept the token")
        if claims.kind != kind:
            raise TokenRejectedError(f"expected a {kind} token")
        if session is not None and claims.session != session:
            raise TokenRejectedError("token is for another session")
        return claims

    async def _ask_about_token(self, token: str) -> TunnelClaims | None:
        answer = await self._api.validate(token)
        return None if answer is None else _claims_of(answer)

    async def _ask_about_grant(self, grant: str) -> TunnelClaims | None:
        answer = await self._api.check_grant(grant)
        if answer is None:
            return None
        return TunnelClaims(answer.session, TokenKind.VIEW, answer.user, answer.expires_at)

    async def _cached(
        self, key: str, ask: Callable[[], Awaitable[TunnelClaims | None]]
    ) -> TunnelClaims | None:
        now = self._clock()
        self._forget_unusable(now)
        cached = self._verdicts.get(key)
        if cached is not None and cached.fresh_until > now:
            return cached.claims
        try:
            claims = await ask()
        except LumlUnavailableError as error:
            self._note_no_answer(error)
            return _stale_claims(cached, now)
        self._relay_token_refused = False
        fresh_until = now + self._cache_window
        if claims is not None:
            fresh_until = min(fresh_until, claims.expires_at.timestamp())
        self._store(key, _Verdict(claims, fresh_until))
        return claims

    def _store(self, key: str, verdict: _Verdict) -> None:
        # Dicts keep insertion order, so re-inserting makes a key the newest.
        self._verdicts.pop(key, None)
        self._verdicts[key] = verdict
        while len(self._verdicts) > self._max_entries:
            del self._verdicts[next(iter(self._verdicts))]

    def _note_no_answer(self, error: LumlUnavailableError) -> None:
        if isinstance(error, RelayTokenRefusedError):
            self._relay_token_refused = True
            logger.error("LUML refused the relay token when asked about a token: %s", error)
        else:
            logger.warning("LUML gave no verdict on a token: %s", error)

    def _forget_unusable(self, now: float) -> None:
        if now < self._next_cleanup:
            return
        self._next_cleanup = now + self._cache_window
        self._verdicts = {
            key: verdict for key, verdict in self._verdicts.items() if verdict.usable(now)
        }


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _claims_of(answer: ActiveToken) -> TunnelClaims | None:
    if answer.kind not in tuple(TokenKind):
        return None
    return TunnelClaims(answer.session, TokenKind(answer.kind), answer.user, answer.expires_at)


def _stale_claims(cached: _Verdict | None, now: float) -> TunnelClaims:
    # A refusal past its window is not reused: it has no expiry of its own to bound it.
    if cached is None or cached.claims is None or not cached.usable(now):
        raise TokenCheckUnavailableError("LUML cannot be asked about the token")
    return cached.claims
