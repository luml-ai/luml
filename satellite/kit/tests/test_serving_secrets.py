from typing import Any

import pytest

from luml_satellite.serving import PlatformSecretSource, SecretUnavailable


class SecretPlatform:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.values: dict[str, dict[str, Any] | Exception] = {
            "secret-1": {"name": "api key", "value": "first"}
        }

    async def get_orbit_secret(self, secret_id: str) -> dict[str, object]:
        self.calls.append(secret_id)
        value = self.values[secret_id]
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.asyncio
async def test_platform_secret_source_caches_each_secret_for_one_minute() -> None:
    now = [0.0]
    platform = SecretPlatform()
    source = PlatformSecretSource(platform, clock=lambda: now[0])

    first = await source.resolve("deployment", {"api_key": "secret-1"})
    platform.values["secret-1"] = {"name": "api key", "value": "second"}
    now[0] = 59.0
    cached = await source.resolve("deployment", {"api_key": "secret-1"})
    now[0] = 60.0
    refreshed = await source.resolve("deployment", {"api_key": "secret-1"})

    assert first == cached == {"api_key": "first"}
    assert refreshed == {"api_key": "second"}
    assert platform.calls == ["secret-1", "secret-1"]


@pytest.mark.asyncio
async def test_platform_secret_source_names_and_does_not_cache_failures() -> None:
    platform = SecretPlatform()
    platform.values["secret-1"] = RuntimeError("platform unavailable")
    source = PlatformSecretSource(platform)

    with pytest.raises(SecretUnavailable, match="api_key"):
        await source.resolve("deployment", {"api_key": "secret-1"})
    platform.values["secret-1"] = {"name": "api key", "value": "recovered"}

    assert await source.resolve("deployment", {"api_key": "secret-1"}) == {"api_key": "recovered"}
    assert platform.calls == ["secret-1", "secret-1"]
