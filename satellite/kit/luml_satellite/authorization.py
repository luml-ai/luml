import hashlib
import logging
import time
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
        self._cache: dict[str, _CachedVerdict] = {}

    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        cache_key = hashlib.sha256(api_key.encode()).hexdigest()
        now = self._clock()
        cached = self._cache.get(cache_key)
        if cached is not None and cached.expires_at > now:
            return cached.verdict

        try:
            allowed = await self._platform.authorize_inference_access(api_key)
        except Exception:
            self._cache.pop(cache_key, None)
            self._logger.warning("inference authorization is unavailable")
            return AuthorizationVerdict.UNAVAILABLE

        verdict = AuthorizationVerdict.ALLOWED if allowed else AuthorizationVerdict.DENIED
        self._cache[cache_key] = _CachedVerdict(verdict, self._clock() + self._ttl_seconds)
        return verdict
