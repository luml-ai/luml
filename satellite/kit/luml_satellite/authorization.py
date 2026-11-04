import hashlib
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AuthorizationVerdict(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"


class Authorizer(Protocol):
    async def authorize(self, api_key: str) -> AuthorizationVerdict: ...


class InferenceAuthorizationPlatform(Protocol):
    async def authorize_inference_access(self, api_key: str) -> bool: ...


class _VerdictCache[T]:
    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._next_cleanup = 0.0

    def get(self, key: str, now: float) -> T | None:
        if now >= self._next_cleanup:
            for expired_key, (_, expires_at) in list(self._entries.items()):
                if expires_at <= now:
                    del self._entries[expired_key]
            self._next_cleanup = now + 60.0
        cached = self._entries.get(key)
        if cached is None:
            return None
        value, expires_at = cached
        if expires_at <= now:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: str, value: T, expires_at: float) -> None:
        self._entries[key] = (value, expires_at)
        self._entries.move_to_end(key)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def discard(self, key: str) -> None:
        self._entries.pop(key, None)


@dataclass(frozen=True)
class _CachedVerdict:
    verdict: AuthorizationVerdict
    expires_at: float


class PlatformAuthorizer:
    def __init__(
        self,
        platform: InferenceAuthorizationPlatform,
        *,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._platform = platform
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._logger = logger or logging.getLogger("luml_satellite.authorization")
        self._cache = _VerdictCache[_CachedVerdict](1024)
        self._denied_cache = _VerdictCache[_CachedVerdict](64)

    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        cache_key = hashlib.sha256(api_key.encode()).hexdigest()
        now = self._clock()
        cached = self._cache.get(cache_key, now)
        denied = self._denied_cache.get(cache_key, now)
        if cached is None:
            cached = denied
        if cached is not None and cached.expires_at > now:
            return cached.verdict

        try:
            allowed = await self._platform.authorize_inference_access(api_key)
        except Exception:
            self._cache.discard(cache_key)
            self._denied_cache.discard(cache_key)
            self._logger.warning("inference authorization is unavailable")
            return AuthorizationVerdict.UNAVAILABLE

        verdict = AuthorizationVerdict.ALLOWED if allowed else AuthorizationVerdict.DENIED
        cached = _CachedVerdict(verdict, self._clock() + self._ttl_seconds)
        if allowed:
            self._denied_cache.discard(cache_key)
            self._cache.put(cache_key, cached, cached.expires_at)
        else:
            self._cache.discard(cache_key)
            self._denied_cache.put(cache_key, cached, cached.expires_at)
        return verdict
