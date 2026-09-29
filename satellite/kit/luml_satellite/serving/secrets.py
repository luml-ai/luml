import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from luml_satellite.wire import Secret


class SecretUnavailable(RuntimeError):
    def __init__(self, attribute: str) -> None:
        self.attribute = attribute
        super().__init__(f"secret-backed attribute '{attribute}' is unavailable")


class SecretSource(Protocol):
    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]: ...


class SecretPlatform(Protocol):
    async def get_orbit_secret(self, secret_id: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class _CachedSecret:
    value: str
    expires_at: float


class PlatformSecretSource:
    def __init__(
        self,
        platform: SecretPlatform,
        *,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._platform = platform
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._cache: dict[str, _CachedSecret] = {}

    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        del deployment_id
        resolved: dict[str, str] = {}
        for attribute, secret_id in secrets.items():
            resolved[attribute] = await self._resolve_one(attribute, secret_id)
        return resolved

    async def _resolve_one(self, attribute: str, secret_id: str) -> str:
        now = self._clock()
        cached = self._cache.get(secret_id)
        if cached is not None and cached.expires_at > now:
            return cached.value
        try:
            payload = await self._platform.get_orbit_secret(secret_id)
            value = Secret.model_validate(payload).value
        except Exception as error:
            self._cache.pop(secret_id, None)
            raise SecretUnavailable(attribute) from error
        self._cache[secret_id] = _CachedSecret(value, self._clock() + self._ttl_seconds)
        return value


class UnavailableSecretSource:
    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        del deployment_id
        if secrets:
            raise SecretUnavailable(next(iter(secrets)))
        return {}
