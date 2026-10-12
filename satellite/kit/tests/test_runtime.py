import asyncio
import logging

import httpx
import pytest

from luml_satellite import (
    AuthenticationFailure,
    PlatformClient,
    SatelliteConfiguration,
    SatelliteRuntime,
)
from luml_satellite.testing import (
    FakeClock,
    FakeDriver,
    FakeMonitoringBundle,
    FakePlatform,
    FakeServingPlacement,
)
from luml_satellite.workload import StartResult, StartStatus, WorkloadObservation, WorkloadState
from tests.helpers import DEPLOYMENT_ID, TASK_ID, deployment_record, task_record


def configuration(
    token: str = "test-token",
    *,
    monitoring: bool = False,
    health_interval: float = 60,
    base_url: str | None = "http://satellite",
) -> SatelliteConfiguration:
    return SatelliteConfiguration.model_validate(
        {
            "SATELLITE_TOKEN": token,
            "PLATFORM_URL": "http://platform",
            "BASE_URL": base_url,
            "MONITORING_ENABLED": monitoring,
            "POLL_INTERVAL_SEC": 1,
            "POLL_BACKOFF_MAX_SEC": 8,
            "HEALTH_PASS_INTERVAL_SEC": health_interval,
        }
    )


class PairRetryRuntime(SatelliteRuntime):
    async def reconcile(self) -> None:
        return None

    async def poll(self) -> None:
        self.stop()


class ActualOnePassRuntime(SatelliteRuntime):
    async def poll(self) -> None:
        await super().poll()
        await self.polling.drain()
        self.stop()


class FailingLoopRuntime(SatelliteRuntime):
    poll_attempts: int = 0

    async def pair(self) -> None:
        return None

    async def reconcile(self) -> None:
        return None

    async def poll(self) -> None:
        self.poll_attempts += 1
        if self.poll_attempts == 10:
            self.stop()
        if self.poll_attempts == 2:
            raise AuthenticationFailure(
                "platform returned 401",
                status_code=401,
                detail="invalid token",
            )
        raise RuntimeError(f"failure {self.poll_attempts}")


class LifecycleRuntime(SatelliteRuntime):
    pair_calls: int = 0

    async def pair(self) -> None:
        self.pair_calls += 1
        return None

    async def reconcile(self) -> None:
        return None

    async def poll(self) -> None:
        self.stop()


class CloseableServingPlacement(FakeServingPlacement):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class DisabledHealthRuntime(SatelliteRuntime):
    poll_attempts: int = 0
    health_passes: int = 0

    async def pair(self) -> None:
        return None

    async def reconcile(self) -> None:
        return None

    async def poll(self) -> None:
        self.poll_attempts += 1
        if self.poll_attempts == 2:
            self.stop()

    async def health_pass(self) -> None:
        self.health_passes += 1


@pytest.mark.asyncio
async def test_runtime_retries_pairing_with_backoff() -> None:
    platform = FakePlatform()
    platform.script_responses(
        "POST",
        "/satellites/v1/pair",
        (503, {"detail": "starting"}),
        None,
    )
    clock = FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = PairRetryRuntime(
            configuration(),
            client,
            FakeDriver(),
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        await runtime.run_forever()

    pairing_requests = [
        request
        for request in platform.requests
        if request.method == "POST" and request.path == "/satellites/v1/pair"
    ]
    assert len(pairing_requests) == 2
    assert clock.sleeps == [1.0]


@pytest.mark.asyncio
async def test_runtime_reports_the_paired_satellite() -> None:
    platform = FakePlatform()
    paired_ids: list[str] = []
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = SatelliteRuntime(
            configuration(),
            client,
            FakeDriver(),
            on_paired=lambda paired: paired_ids.append(paired.id),
        )
        await runtime.pair()

    assert paired_ids == [platform.satellite_id]


@pytest.mark.asyncio
async def test_runtime_retries_when_an_older_platform_requires_an_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    platform.script_responses(
        "POST",
        "/satellites/v1/pair",
        (
            422,
            [
                {
                    "type": "missing",
                    "loc": ["body", "base_url"],
                    "msg": "Field required",
                }
            ],
        ),
        None,
    )
    clock = FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = PairRetryRuntime(
            configuration(base_url=None),
            client,
            FakeDriver(),
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        await runtime.run_forever()

    pairing_requests = [
        request
        for request in platform.requests
        if request.method == "POST" and request.path == "/satellites/v1/pair"
    ]
    assert len(pairing_requests) == 2
    for request in pairing_requests:
        assert isinstance(request.body, dict)
        assert "base_url" not in request.body
    assert clock.sleeps == [1.0]
    assert "this platform requires BASE_URL; set BASE_URL or upgrade the platform" in caplog.text


@pytest.mark.asyncio
async def test_runtime_reconciles_before_polling_without_an_http_application() -> None:
    platform = FakePlatform()
    deployment_id = "10000000-0000-0000-0000-000000000041"
    platform.add_deployment(
        deployment_record(
            id=deployment_id,
            status="active",
            inference_url=f"/deployments/{deployment_id}",
        )
    )
    driver = FakeDriver()
    driver.add_workload(
        deployment_id,
        observation=WorkloadObservation(
            WorkloadState.READY,
            upstream_url="http://model",
            launcher_protocol=driver.launcher_protocol,
        ),
    )
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = ActualOnePassRuntime(
            configuration(),
            client,
            driver,
            jitter=lambda ceiling: ceiling,
        )
        assert runtime.public_application is None
        assert runtime.internal_application is None
        await runtime.run_forever()

    deployment_listing = next(
        index
        for index, request in enumerate(platform.requests)
        if request.path == "/satellites/v1/deployments"
    )
    running_tasks = next(
        index
        for index, request in enumerate(platform.requests)
        if request.path == "/satellites/v1/tasks" and request.query == {"status": ["running"]}
    )
    pending_tasks = next(
        index
        for index, request in enumerate(platform.requests)
        if request.path == "/satellites/v1/tasks" and request.query == {"status": ["pending"]}
    )
    assert deployment_listing < running_tasks < pending_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "failures", "expected_sleeps"),
    [(502, 1, [1.0]), (503, 1, [1.0]), (503, 5, [1.0, 2.0, 4.0, 8.0, 8.0])],
)
async def test_runtime_retries_running_task_recovery_before_polling(
    status_code: int,
    failures: int,
    expected_sleeps: list[float],
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record(status="active"))
    platform.add_task(task_record(status="running", started_at="2026-01-01T00:00:00+00:00"))
    platform.script_responses(
        "GET",
        "/satellites/v1/tasks",
        *[(status_code, {"detail": "temporarily unavailable"})] * failures,
    )
    clock = FakeClock()
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=WorkloadObservation(
            WorkloadState.READY,
            upstream_url="http://model",
            launcher_protocol=driver.launcher_protocol,
        ),
    )
    serving = FakeServingPlacement()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = ActualOnePassRuntime(
            configuration(),
            client,
            driver,
            serving=serving,
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        await runtime.run_forever()

    task_listings = [
        request.query
        for request in platform.requests
        if request.method == "GET" and request.path == "/satellites/v1/tasks"
    ]
    assert task_listings == [{"status": ["running"]}] * (failures + 1) + [{"status": ["pending"]}]
    assert clock.sleeps == expected_sleeps
    assert platform.tasks[TASK_ID]["status"] == "done"
    assert len(serving.register_calls) == 1
    assert len(driver.sweep_calls) == 1
    assert "could not resume running tasks during reconciliation; retrying" in caplog.text


@pytest.mark.asyncio
async def test_runtime_retries_running_task_timeout_with_fresh_backoff() -> None:
    platform = FakePlatform()
    platform.script_responses(
        "GET", "/satellites/v1/deployments", (503, {"detail": "temporarily unavailable"})
    )
    transport = platform.transport
    running_requests = 0

    async def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal running_requests
        if request.url.path == "/satellites/v1/tasks" and request.url.params["status"] == "running":
            running_requests += 1
            if running_requests == 1:
                raise httpx.ReadTimeout("running task listing timed out", request=request)
        return await transport.handle_async_request(request)

    clock = FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=httpx.MockTransport(handle_request),
    ) as client:
        runtime = ActualOnePassRuntime(
            configuration(),
            client,
            FakeDriver(),
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        await runtime.run_forever()

    assert running_requests == 2
    assert clock.sleeps == [1.0, 1.0]
    assert platform.requests[-1].query == {"status": ["pending"]}


@pytest.mark.asyncio
async def test_running_task_recovery_stays_alive_and_can_be_cancelled() -> None:
    class BlockingClock(FakeClock):
        def __init__(self) -> None:
            super().__init__()
            self.sleeping = asyncio.Event()

        async def sleep(self, seconds: float) -> None:
            await super().sleep(seconds)
            self.sleeping.set()
            await asyncio.Event().wait()

    platform = FakePlatform()
    platform.script_responses(
        "GET", "/satellites/v1/tasks", (503, {"detail": "temporarily unavailable"})
    )
    clock = BlockingClock()
    driver = FakeDriver()
    monitoring = FakeMonitoringBundle()
    serving = CloseableServingPlacement()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = ActualOnePassRuntime(
            configuration(monitoring=True),
            client,
            driver,
            monitoring=monitoring,
            serving=serving,
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        runtime_task = asyncio.create_task(runtime.run_forever())
        try:
            await asyncio.wait_for(clock.sleeping.wait(), timeout=1)
            assert not runtime_task.done()
            assert driver.sweep_calls == []
            assert monitoring.started is True
            assert monitoring.closed is False
            assert serving.closed is False
        finally:
            runtime_task.cancel()
            result = await asyncio.gather(runtime_task, return_exceptions=True)

    assert isinstance(result[0], asyncio.CancelledError)
    assert monitoring.closed is True
    assert serving.closed is True


@pytest.mark.asyncio
async def test_runtime_loop_uses_capped_backoff_and_names_authentication_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    clock = FakeClock()
    caplog.set_level(logging.WARNING, logger="luml_satellite.runtime")
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = FailingLoopRuntime(
            configuration(),
            client,
            FakeDriver(),
            clock=clock,
            jitter=lambda ceiling: ceiling,
        )
        await runtime.run_forever()

    assert runtime.poll_attempts == 10
    assert clock.sleeps == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0]
    assert "platform rejected the satellite token; re-pair this satellite" in caplog.text
    errors = [
        record
        for record in caplog.records
        if record.name == "luml_satellite.runtime" and record.levelno >= logging.ERROR
    ]
    assert len(errors) == 1
    assert "five consecutive times" in errors[0].getMessage()


@pytest.mark.asyncio
async def test_runtime_starts_monitoring_and_closes_monitoring_and_serving() -> None:
    platform = FakePlatform()
    monitoring = FakeMonitoringBundle()
    serving = CloseableServingPlacement()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = LifecycleRuntime(
            configuration(monitoring=True),
            client,
            FakeDriver(),
            monitoring=monitoring,
            serving=serving,
        )
        await runtime.run_forever()

    assert monitoring.started is True
    assert monitoring.closed is True
    assert serving.closed is True
    assert "monitoring" in runtime.capabilities


@pytest.mark.asyncio
async def test_stop_before_run_is_not_lost() -> None:
    platform = FakePlatform()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = LifecycleRuntime(
            configuration(),
            client,
            FakeDriver(),
        )
        runtime.stop()

        await runtime.run_forever()

    assert runtime.pair_calls == 0


@pytest.mark.asyncio
async def test_zero_health_interval_disables_health_passes() -> None:
    platform = FakePlatform()
    clock = FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        runtime = DisabledHealthRuntime(
            configuration(health_interval=0),
            client,
            FakeDriver(),
            clock=clock,
        )
        await runtime.run_forever()

    assert runtime.poll_attempts == 2
    assert runtime.health_passes == 0


@pytest.mark.asyncio
async def test_two_runtimes_keep_convergence_state_isolated() -> None:
    first_id = "10000000-0000-0000-0000-000000000051"
    second_id = "10000000-0000-0000-0000-000000000052"
    first_task = "20000000-0000-0000-0000-000000000051"
    second_task = "20000000-0000-0000-0000-000000000052"
    first_platform = FakePlatform(token="first-token")
    second_platform = FakePlatform(token="second-token")
    first_platform.add_deployment(deployment_record(id=first_id))
    first_platform.add_task(task_record(id=first_task, payload={"deployment_id": first_id}))
    second_platform.add_deployment(deployment_record(id=second_id))
    second_platform.add_task(task_record(id=second_task, payload={"deployment_id": second_id}))
    first_driver = FakeDriver()
    second_driver = FakeDriver()
    first_driver.script_start(first_id, StartResult(StartStatus.IN_PROGRESS))
    second_driver.script_start(second_id, StartResult(StartStatus.IN_PROGRESS))

    async with (
        PlatformClient(
            "http://first",
            first_platform.token,
            transport=first_platform.transport,
        ) as first_client,
        PlatformClient(
            "http://second",
            second_platform.token,
            transport=second_platform.transport,
        ) as second_client,
    ):
        first_runtime = SatelliteRuntime(
            configuration("first-token"),
            first_client,
            first_driver,
        )
        second_runtime = SatelliteRuntime(
            configuration("second-token"),
            second_client,
            second_driver,
        )
        await asyncio.gather(first_runtime.poll(), second_runtime.poll())
        await asyncio.gather(first_runtime.polling.drain(), second_runtime.polling.drain())

    assert set(first_runtime.convergence.in_progress) == {first_id}
    assert set(second_runtime.convergence.in_progress) == {second_id}
    assert [str(call[0].id) for call in first_driver.start_calls] == [first_id]
    assert [str(call[0].id) for call in second_driver.start_calls] == [second_id]
