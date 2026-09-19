import asyncio
from collections.abc import AsyncIterator, Set
from contextlib import asynccontextmanager

import pytest

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    Deployment,
    PlatformClient,
    PollingPass,
    SatelliteQueueTask,
    TokenDeriver,
)
from luml_satellite.testing import FakeClock, FakeDriver, FakePlatform, FakeServingPlacement
from luml_satellite.workload import (
    UNSUPPORTED,
    BulkObservation,
    StartContext,
    StartResult,
    StartStatus,
    WorkloadObservation,
)
from tests.helpers import DEPLOYMENT_ID, TASK_ID, deployment_record, task_record


@asynccontextmanager
async def polling_kit(
    platform: FakePlatform,
    driver: FakeDriver,
    *,
    max_parallel: int = 8,
    driver_call_timeout: float = 1.0,
    clock: FakeClock | None = None,
) -> AsyncIterator[tuple[Convergence, PollingPass]]:
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        convergence = Convergence(
            client,
            driver,
            ArtifactResolver(
                client,
                TokenDeriver("satellite-token"),
                satellite_address="http://satellite",
            ),
            serving=FakeServingPlacement(),
            max_parallel=max_parallel,
            driver_call_timeout=driver_call_timeout,
            clock=clock,
        )
        yield convergence, PollingPass(client, convergence)


def add_deploy(
    platform: FakePlatform,
    deployment_id: str,
    task_id: str,
    *,
    task_type: str = "deploy",
    status: str = "pending",
) -> None:
    platform.add_deployment(deployment_record(id=deployment_id, status=status))
    platform.add_task(
        task_record(
            id=task_id,
            type=task_type,
            payload={"deployment_id": deployment_id},
        )
    )


class BlockingDriver(FakeDriver):
    def __init__(self, blocked_id: str) -> None:
        super().__init__()
        self.blocked_id = blocked_id
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.active_starts = 0
        self.max_active_starts = 0

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        deployment_id = str(deployment.id)
        self.active_starts += 1
        self.max_active_starts = max(self.max_active_starts, self.active_starts)
        try:
            if deployment_id == self.blocked_id:
                self.entered.set()
                await self.release.wait()
            return await super().start(deployment, context)
        finally:
            self.active_starts -= 1


@pytest.mark.asyncio
async def test_deployments_run_in_parallel_but_tasks_for_one_deployment_are_serial() -> None:
    platform = FakePlatform()
    deployment_a = "10000000-0000-0000-0000-0000000000a1"
    deployment_b = "10000000-0000-0000-0000-0000000000b1"
    deployment_c = "10000000-0000-0000-0000-0000000000c1"
    add_deploy(platform, deployment_a, "task-a")
    add_deploy(platform, deployment_b, "task-b")
    add_deploy(platform, deployment_c, "task-c")
    platform.add_task(
        task_record(
            id="task-a-reconcile",
            type="reconcile",
            payload={"deployment_id": deployment_a},
        )
    )
    driver = BlockingDriver(deployment_a)

    async with polling_kit(platform, driver, max_parallel=2) as (_, poller):
        await poller.run()
        await asyncio.wait_for(driver.entered.wait(), timeout=1)
        for _ in range(20):
            if (
                platform.deployments[deployment_b]["status"] == "active"
                and platform.deployments[deployment_c]["status"] == "active"
            ):
                break
            await asyncio.sleep(0)

        assert platform.deployments[deployment_b]["status"] == "active"
        assert platform.deployments[deployment_c]["status"] == "active"
        assert platform.tasks["task-a-reconcile"]["status"] == "pending"
        assert driver.max_active_starts == 2

        driver.release.set()
        await poller.drain()

    assert platform.deployments[deployment_a]["status"] == "active"
    assert platform.tasks["task-a-reconcile"]["status"] == "done"


@pytest.mark.asyncio
async def test_undeploy_waits_for_start_then_supersedes_its_deploy_entry() -> None:
    platform = FakePlatform()
    add_deploy(platform, DEPLOYMENT_ID, TASK_ID)
    undeploy_task_id = "20000000-0000-0000-0000-000000000002"
    platform.add_task(
        task_record(
            id=undeploy_task_id,
            type="undeploy",
            payload={"deployment_id": DEPLOYMENT_ID},
        )
    )
    driver = BlockingDriver(DEPLOYMENT_ID)
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))

    async with polling_kit(platform, driver) as (_, poller):
        await poller.run()
        await asyncio.wait_for(driver.entered.wait(), timeout=1)
        platform.deployments[DEPLOYMENT_ID]["status"] = "deletion_pending"
        driver.release.set()
        await poller.drain()

    assert platform.tasks[TASK_ID]["status"] == "failed"
    assert platform.tasks[TASK_ID]["result"]["reason"] == "superseded by undeploy"
    assert platform.tasks[undeploy_task_id]["status"] == "done"
    assert DEPLOYMENT_ID not in platform.deployments
    assert driver.remove_calls == [DEPLOYMENT_ID]


class HangingStartDriver(FakeDriver):
    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        if str(deployment.id) == DEPLOYMENT_ID:
            await asyncio.Event().wait()
        return await super().start(deployment, context)


@pytest.mark.asyncio
async def test_hung_start_is_bounded_and_releases_the_driver_slot() -> None:
    platform = FakePlatform()
    add_deploy(platform, DEPLOYMENT_ID, TASK_ID)
    deployment_b = "10000000-0000-0000-0000-000000000002"
    task_b = "20000000-0000-0000-0000-000000000002"
    add_deploy(platform, deployment_b, task_b)
    driver = HangingStartDriver()

    async with polling_kit(
        platform,
        driver,
        max_parallel=1,
        driver_call_timeout=0.01,
    ) as (_, poller):
        await poller.run()
        await poller.drain()

    assert platform.tasks[TASK_ID]["status"] == "failed"
    assert platform.tasks[TASK_ID]["result"]["reason"] == "Failed to create container"
    assert "timed out" in platform.tasks[TASK_ID]["result"]["error"]
    assert platform.tasks[task_b]["status"] == "done"
    assert platform.deployments[deployment_b]["status"] == "active"


class HangingObserveDriver(FakeDriver):
    async def observe_all(self, deployment_ids: Set[str]) -> BulkObservation:
        self.observe_all_calls.append(set(deployment_ids))
        return UNSUPPORTED

    async def observe(self, deployment_id: str) -> WorkloadObservation:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_hung_observe_counts_as_unknown_until_the_deadline() -> None:
    platform = FakePlatform()
    add_deploy(platform, DEPLOYMENT_ID, TASK_ID)
    driver = HangingObserveDriver()
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    clock = FakeClock()

    async with polling_kit(
        platform,
        driver,
        driver_call_timeout=0.01,
        clock=clock,
    ) as (convergence, poller):
        await poller.run()
        await poller.drain()
        await poller.run()
        assert DEPLOYMENT_ID in convergence.in_progress

        clock.now = 1801
        await poller.run()
        assert DEPLOYMENT_ID not in convergence.in_progress

    assert platform.tasks[TASK_ID]["result"]["reason"] == "healthcheck timeout"


@pytest.mark.asyncio
async def test_unknown_invalid_and_custom_tasks_do_not_stop_the_pass() -> None:
    platform = FakePlatform()
    unknown_id = "20000000-0000-0000-0000-000000000011"
    custom_id = "20000000-0000-0000-0000-000000000012"
    invalid_id = "20000000-0000-0000-0000-000000000013"
    platform.add_task(task_record(id=unknown_id, type="vendor.unknown", payload=None))
    platform.add_task(task_record(id=custom_id, type="vendor.sync", payload=None))
    platform.add_task(task_record(id=invalid_id, type="deploy", payload={}))
    handled: list[str] = []

    async def custom_handler(task: SatelliteQueueTask) -> None:
        handled.append(task.id)

    async with PlatformClient(
        "http://platform", platform.token, transport=platform.transport
    ) as client:
        convergence = Convergence(
            client,
            FakeDriver(),
            ArtifactResolver(
                client,
                TokenDeriver("token"),
                satellite_address="http://satellite",
            ),
        )
        poller = PollingPass(
            client,
            convergence,
            custom_handlers={"vendor.sync": custom_handler},
        )
        await poller.run()
        await poller.drain()

    assert platform.tasks[unknown_id]["result"] == {"reason": "unknown type: vendor.unknown"}
    assert platform.tasks[invalid_id]["result"] == {"reason": "invalid task payload"}
    assert handled == [custom_id]
    assert platform.tasks[custom_id]["status"] == "pending"
    assert all(item.resource_id != custom_id for item in platform.task_transitions)


@pytest.mark.asyncio
async def test_invalid_tasks_are_failed_before_valid_tasks_are_scheduled() -> None:
    platform = FakePlatform()
    add_deploy(platform, DEPLOYMENT_ID, TASK_ID)
    unknown_id = "20000000-0000-0000-0000-000000000017"
    platform.add_task(task_record(id=unknown_id, type="vendor.unknown", payload=None))

    async with polling_kit(platform, FakeDriver()) as (_, poller):
        await poller.run()
        await poller.drain()

    task_transitions = [
        (transition.resource_id, transition.status) for transition in platform.task_transitions
    ]
    assert task_transitions == [
        (unknown_id, "failed"),
        (TASK_ID, "running"),
        (TASK_ID, "done"),
    ]


@pytest.mark.asyncio
async def test_custom_handler_exception_fails_the_task_without_stopping_the_pass() -> None:
    platform = FakePlatform()
    custom_id = "20000000-0000-0000-0000-000000000016"
    platform.add_task(task_record(id=custom_id, type="vendor.sync", payload=None))

    async def custom_handler(task: SatelliteQueueTask) -> None:
        raise RuntimeError(f"vendor rejected {task.id}")

    async with PlatformClient(
        "http://platform", platform.token, transport=platform.transport
    ) as client:
        convergence = Convergence(
            client,
            FakeDriver(),
            ArtifactResolver(
                client,
                TokenDeriver("token"),
                satellite_address="http://satellite",
            ),
        )
        poller = PollingPass(
            client,
            convergence,
            custom_handlers={"vendor.sync": custom_handler},
        )
        await poller.run()
        await poller.drain()

    assert platform.tasks[custom_id]["status"] == "failed"
    assert platform.tasks[custom_id]["result"] == {
        "reason": f"handler error: vendor rejected {custom_id}"
    }


@pytest.mark.asyncio
async def test_unparseable_task_and_handler_exception_are_failed_without_stopping() -> None:
    platform = FakePlatform()
    malformed_id = "20000000-0000-0000-0000-000000000014"
    handler_error_id = "20000000-0000-0000-0000-000000000015"
    platform.add_task(task_record(id=malformed_id, scheduled_at="not-a-date"))
    platform.add_task(task_record(id=handler_error_id))
    platform.script_responses(
        "POST",
        f"/satellites/v1/tasks/{handler_error_id}/status",
        (500, {"detail": "running write failed"}),
    )

    async with polling_kit(platform, FakeDriver()) as (_, poller):
        await poller.run()
        await poller.drain()

    assert platform.tasks[malformed_id]["result"] == {"reason": "invalid task payload"}
    assert platform.tasks[handler_error_id]["status"] == "failed"
    assert platform.tasks[handler_error_id]["result"]["reason"].startswith("handler error:")


@pytest.mark.asyncio
async def test_custom_task_without_a_deployment_id_is_tracked_only_once() -> None:
    platform = FakePlatform()
    custom_id = "20000000-0000-0000-0000-000000000021"
    platform.add_task(task_record(id=custom_id, type="vendor.wait", payload=None))
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def custom_handler(task: SatelliteQueueTask) -> None:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()

    async with PlatformClient(
        "http://platform", platform.token, transport=platform.transport
    ) as client:
        convergence = Convergence(
            client,
            FakeDriver(),
            ArtifactResolver(
                client,
                TokenDeriver("token"),
                satellite_address="http://satellite",
            ),
        )
        poller = PollingPass(
            client,
            convergence,
            custom_handlers={"vendor.wait": custom_handler},
        )
        await poller.run()
        await asyncio.wait_for(entered.wait(), timeout=1)
        await poller.run()
        assert poller.in_flight == frozenset({custom_id})
        release.set()
        await poller.drain()

    assert calls == 1
    assert platform.tasks[custom_id]["status"] == "pending"


@pytest.mark.asyncio
async def test_custom_tasks_without_deployment_ids_share_the_concurrency_bound() -> None:
    platform = FakePlatform()
    task_ids = [
        "20000000-0000-0000-0000-000000000022",
        "20000000-0000-0000-0000-000000000023",
    ]
    for task_id in task_ids:
        platform.add_task(task_record(id=task_id, type="vendor.wait", payload=None))

    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    active = 0
    max_active = 0

    async def custom_handler(task: SatelliteQueueTask) -> None:
        nonlocal active, calls, max_active
        calls += 1
        active += 1
        max_active = max(max_active, active)
        entered.set()
        try:
            await release.wait()
        finally:
            active -= 1

    async with PlatformClient(
        "http://platform", platform.token, transport=platform.transport
    ) as client:
        convergence = Convergence(
            client,
            FakeDriver(),
            ArtifactResolver(
                client,
                TokenDeriver("token"),
                satellite_address="http://satellite",
            ),
            max_parallel=1,
        )
        poller = PollingPass(
            client,
            convergence,
            custom_handlers={"vendor.wait": custom_handler},
        )
        await poller.run()
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert calls == 1
        assert poller.in_flight == frozenset(task_ids)
        release.set()
        await poller.drain()

    assert calls == 2
    assert max_active == 1
    assert all(platform.tasks[task_id]["status"] == "pending" for task_id in task_ids)
