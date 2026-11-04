import logging
from collections import deque

import pytest

from luml_satellite.authorization import AuthorizationVerdict, PlatformAuthorizer


class AuthorizationPlatform:
    def __init__(self, *answers: bool | Exception) -> None:
        self.answers = deque(answers)
        self.calls: list[str] = []

    async def authorize_inference_access(self, api_key: str) -> bool:
        self.calls.append(api_key)
        answer = self.answers.popleft()
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.mark.asyncio
async def test_platform_authorizer_caches_allowed_and_denied_verdicts_per_instance() -> None:
    now = [10.0]
    platform = AuthorizationPlatform(True, False, False)
    first = PlatformAuthorizer(platform, clock=lambda: now[0])
    second = PlatformAuthorizer(platform, clock=lambda: now[0])

    assert await first.authorize("allowed-key") is AuthorizationVerdict.ALLOWED
    assert await first.authorize("allowed-key") is AuthorizationVerdict.ALLOWED
    assert await first.authorize("denied-key") is AuthorizationVerdict.DENIED
    assert await first.authorize("denied-key") is AuthorizationVerdict.DENIED
    assert await second.authorize("allowed-key") is AuthorizationVerdict.DENIED
    assert platform.calls == ["allowed-key", "denied-key", "allowed-key"]
    assert "allowed-key" not in repr(first._cache._entries)
    assert "denied-key" not in repr(first._denied_cache._entries)


@pytest.mark.asyncio
async def test_platform_authorizer_refreshes_after_one_minute() -> None:
    now = [10.0]
    platform = AuthorizationPlatform(True, False)
    authorizer = PlatformAuthorizer(platform, clock=lambda: now[0])

    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    now[0] = 69.999
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    now[0] = 70.0
    assert await authorizer.authorize("key") is AuthorizationVerdict.DENIED
    assert platform.calls == ["key", "key"]


@pytest.mark.asyncio
async def test_platform_authorizer_ttl_starts_when_the_platform_answers() -> None:
    now = [10.0]

    class SlowAuthorizationPlatform:
        def __init__(self) -> None:
            self.calls = 0

        async def authorize_inference_access(self, api_key: str) -> bool:
            self.calls += 1
            now[0] += 30
            return self.calls == 1

    platform = SlowAuthorizationPlatform()
    authorizer = PlatformAuthorizer(platform, clock=lambda: now[0])

    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    now[0] = 99.999
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    now[0] = 100.0
    assert await authorizer.authorize("key") is AuthorizationVerdict.DENIED
    assert platform.calls == 2


@pytest.mark.asyncio
async def test_platform_authorizer_reports_unavailable_without_caching_it() -> None:
    platform = AuthorizationPlatform(RuntimeError("platform down for secret-key"), True)
    authorizer = PlatformAuthorizer(platform)

    assert await authorizer.authorize("key") is AuthorizationVerdict.UNAVAILABLE
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    assert platform.calls == ["key", "key"]


@pytest.mark.asyncio
async def test_platform_authorizer_never_logs_the_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = AuthorizationPlatform(RuntimeError("request contained secret-key"))
    authorizer = PlatformAuthorizer(platform)

    with caplog.at_level(logging.WARNING):
        assert await authorizer.authorize("secret-key") is AuthorizationVerdict.UNAVAILABLE

    assert "secret-key" not in caplog.text


def test_platform_authorizer_requires_a_positive_ttl() -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        PlatformAuthorizer(AuthorizationPlatform(), ttl_seconds=0)


@pytest.mark.asyncio
async def test_platform_authorizer_bounds_allowed_cache_and_evicts_least_recently_used() -> None:
    platform = AuthorizationPlatform(*([True] * 1027))
    authorizer = PlatformAuthorizer(platform, clock=lambda: 0.0)

    for index in range(1024):
        assert await authorizer.authorize(f"key-{index}") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("key-0") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("key-1024") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("key-0") is AuthorizationVerdict.ALLOWED
    assert platform.calls.count("key-0") == 1
    assert await authorizer.authorize("key-1") is AuthorizationVerdict.ALLOWED
    assert platform.calls.count("key-1") == 2
    assert len(authorizer._cache._entries) == 1024


@pytest.mark.asyncio
async def test_platform_authorizer_bounds_denials_without_evicting_allowed_keys() -> None:
    platform = AuthorizationPlatform(True, *([False] * 10001))
    authorizer = PlatformAuthorizer(platform, clock=lambda: 0.0)
    assert await authorizer.authorize("allowed-key") is AuthorizationVerdict.ALLOWED

    for index in range(10000):
        assert await authorizer.authorize(f"denied-{index}") is AuthorizationVerdict.DENIED
    assert len(authorizer._denied_cache._entries) == 64
    assert await authorizer.authorize("denied-9999") is AuthorizationVerdict.DENIED
    assert platform.calls.count("denied-9999") == 1
    assert await authorizer.authorize("denied-0") is AuthorizationVerdict.DENIED
    assert platform.calls.count("denied-0") == 2
    assert await authorizer.authorize("allowed-key") is AuthorizationVerdict.ALLOWED
    assert platform.calls.count("allowed-key") == 1


@pytest.mark.asyncio
async def test_platform_authorizer_periodically_removes_unrelated_expired_entries() -> None:
    now = [0.0]
    platform = AuthorizationPlatform(True, False, RuntimeError("unavailable"))
    authorizer = PlatformAuthorizer(platform, clock=lambda: now[0])
    await authorizer.authorize("allowed-key")
    await authorizer.authorize("denied-key")

    now[0] = 60.0
    assert await authorizer.authorize("unrelated-key") is AuthorizationVerdict.UNAVAILABLE
    assert not authorizer._cache._entries
    assert not authorizer._denied_cache._entries
