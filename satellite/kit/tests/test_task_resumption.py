from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    PlatformClient,
    PollingPass,
    Reconciliation,
    SatelliteQueueTask,
    TokenDeriver,
)
from luml_satellite.testing import FakeClock, FakeDriver, FakePlatform, FakeServingPlacement
from luml_satellite.workload import StartResult, StartStatus, WorkloadObservation, WorkloadState
from tests.helpers import DEPLOYMENT_ID, TASK_ID, deployment_record, task_record


@dataclass
class ResumeHarness:
    driver: FakeDriver
    serving: FakeServingPlacement
    clock: FakeClock
    convergence: Convergence
    polling: PollingPass
    reconciliation: Reconciliation


@asynccontextmanager
async def resume_harness(
    platform: FakePlatform,
    *,
    driver: FakeDriver | None = None,
    serving: FakeServingPlacement | None = None,
    clock: FakeClock | None = None,
    custom_handlers: Mapping[
        str,
        Callable[[SatelliteQueueTask], Awaitable[None]],
    ]
    | None = None,
) -> AsyncIterator[ResumeHarness]:
    active_driver = driver or FakeDriver()
    active_serving = serving or FakeServingPlacement()
    active_clock = clock or FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        convergence = Convergence(
            client,
            active_driver,
            ArtifactResolver(
                client,
                TokenDeriver("satellite-token"),
                satellite_address="http://satellite",
            ),
            serving=active_serving,
            clock=active_clock,
        )
        polling = PollingPass(
            client,
            convergence,
            custom_handlers=custom_handlers,
        )
        reconciliation = Reconciliation(
            client,
            convergence,
            polling,
            clock=active_clock,
            jitter=lambda ceiling: ceiling,
        )
        yield ResumeHarness(
            active_driver,
            active_serving,
            active_clock,
            convergence,
            polling,
            reconciliation,
        )


def running_task(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "status": "running",
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    values.update(overrides)
    return task_record(**values)


def observation(state: WorkloadState) -> WorkloadObservation:
    return WorkloadObservation(
        state,
        upstream_url="http://model",
        launcher_protocol="fake-v1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [WorkloadState.STARTING, WorkloadState.UNKNOWN, WorkloadState.READY],
)
async def test_resumed_deploy_waits_under_the_original_deadline(
    state: WorkloadState,
) -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_task(running_task())
    driver = FakeDriver()
    driver.script_observe(DEPLOYMENT_ID, observation(state))
    serving = FakeServingPlacement()
    if state is WorkloadState.READY:
        serving.script_health(DEPLOYMENT_ID, False)
    clock = FakeClock(now=120)

    async with resume_harness(
        platform,
        driver=driver,
        serving=serving,
        clock=clock,
    ) as kit:
        await kit.polling.resume_running()
        entry = kit.convergence.in_progress[DEPLOYMENT_ID]

    assert entry.deadline == 1800
    assert driver.start_calls == []
    assert all(transition.status != "running" for transition in platform.task_transitions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [WorkloadState.STOPPED, WorkloadState.MISSING, WorkloadState.FAILED],
)
async def test_resumed_deploy_restarts_a_settled_workload_with_a_fresh_deadline(
    state: WorkloadState,
) -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_task(running_task())
    driver = FakeDriver()
    driver.script_observe(DEPLOYMENT_ID, observation(state))
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    clock = FakeClock(now=120)

    async with resume_harness(platform, driver=driver, clock=clock) as kit:
        await kit.polling.resume_running()
        entry = kit.convergence.in_progress[DEPLOYMENT_ID]

    assert entry.deadline == 1920
    assert len(driver.start_calls) == 1
    assert all(transition.status != "running" for transition in platform.task_transitions)


@pytest.mark.asyncio
async def test_resumed_ready_deploy_finalizes_without_starting_again() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_task(running_task())
    driver = FakeDriver()
    driver.script_observe(DEPLOYMENT_ID, observation(WorkloadState.READY))

    async with resume_harness(platform, driver=driver) as kit:
        await kit.polling.resume_running()

    assert driver.start_calls == []
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.tasks[TASK_ID]["status"] == "done"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment_status", "expected_task_status", "expected_reason"),
    [
        ("active", "done", None),
        ("not_responding", "done", None),
        ("failed", "failed", "model failed"),
        ("deletion_pending", "failed", "superseded by undeploy"),
        ("deletion_failed", "failed", "superseded by undeploy"),
    ],
)
async def test_resumed_deploy_closes_from_the_record_state(
    deployment_status: str,
    expected_task_status: str,
    expected_reason: str | None,
) -> None:
    platform = FakePlatform()
    error_message = (
        {"reason": "model failed", "error": "provider error"}
        if deployment_status == "failed"
        else None
    )
    platform.add_deployment(
        deployment_record(
            status=deployment_status,
            inference_url=f"/deployments/{DEPLOYMENT_ID}",
            error_message=error_message,
        )
    )
    platform.add_task(running_task())

    async with resume_harness(platform) as kit:
        await kit.polling.resume_running()

    task = platform.tasks[TASK_ID]
    assert task["status"] == expected_task_status
    if expected_reason is not None:
        assert task["result"]["reason"] == expected_reason


@pytest.mark.asyncio
async def test_resumed_undeploy_treats_an_already_gone_record_as_success() -> None:
    platform = FakePlatform()
    platform.add_task(running_task(type="undeploy"))

    async with resume_harness(platform) as kit:
        await kit.polling.resume_running()

    assert platform.tasks[TASK_ID]["status"] == "done"
    assert platform.tasks[TASK_ID]["result"] == {"container_removed": False}


@pytest.mark.asyncio
async def test_resumed_undeploy_runs_again_without_a_second_running_write() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record(status="deletion_pending"))
    platform.add_task(running_task(type="undeploy"))
    driver = FakeDriver()
    artifact_id = str(platform.deployments[DEPLOYMENT_ID]["artifact_id"])
    driver.add_workload(DEPLOYMENT_ID, artifact_id=artifact_id)

    async with resume_harness(platform, driver=driver) as kit:
        await kit.polling.resume_running()

    assert DEPLOYMENT_ID not in platform.deployments
    assert platform.tasks[TASK_ID]["status"] == "done"
    assert [transition.status for transition in platform.task_transitions] == ["done"]
    assert driver.remove_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_resumed_reconcile_fails_when_the_record_is_gone() -> None:
    platform = FakePlatform()
    platform.add_task(running_task(type="reconcile"))

    async with resume_harness(platform) as kit:
        await kit.polling.resume_running()

    assert platform.tasks[TASK_ID]["status"] == "failed"
    assert platform.tasks[TASK_ID]["result"]["reason"] == "deployment record gone"


@pytest.mark.asyncio
async def test_resumed_reconcile_runs_again_without_a_second_running_write() -> None:
    platform = FakePlatform()
    platform.add_deployment(
        deployment_record(
            status="active",
            inference_url=f"/deployments/{DEPLOYMENT_ID}",
            monitoring_mode="full",
        )
    )
    platform.add_task(running_task(type="reconcile"))
    serving = FakeServingPlacement()

    async with resume_harness(platform, serving=serving) as kit:
        await kit.polling.resume_running()

    assert platform.tasks[TASK_ID]["status"] == "done"
    assert [transition.status for transition in platform.task_transitions] == ["done"]
    assert DEPLOYMENT_ID in serving.registered


@pytest.mark.asyncio
async def test_running_invalid_unknown_and_custom_tasks_are_resumed_independently() -> None:
    platform = FakePlatform()
    invalid_id = "20000000-0000-0000-0000-000000000011"
    missing_id = "20000000-0000-0000-0000-000000000012"
    unknown_id = "20000000-0000-0000-0000-000000000013"
    custom_id = "20000000-0000-0000-0000-000000000014"
    platform.add_task(running_task(id=invalid_id, scheduled_at="not-a-date"))
    platform.add_task(running_task(id=missing_id, payload={}))
    platform.add_task(running_task(id=unknown_id, type="vendor.unknown", payload=None))
    platform.add_task(running_task(id=custom_id, type="vendor.sync", payload=None))
    handled: list[str] = []

    async def custom_handler(task: SatelliteQueueTask) -> None:
        handled.append(task.id)

    async with resume_harness(
        platform,
        custom_handlers={"vendor.sync": custom_handler},
    ) as kit:
        await kit.reconciliation.run()

    assert platform.tasks[invalid_id]["result"] == {"reason": "invalid task payload"}
    assert platform.tasks[missing_id]["result"] == {"reason": "invalid task payload"}
    assert platform.tasks[unknown_id]["result"] == {"reason": "unknown type: vendor.unknown"}
    assert handled == [custom_id]
    assert platform.tasks[custom_id]["status"] == "running"


@pytest.mark.asyncio
async def test_reconciliation_resumes_tasks_before_orphan_cleanup() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record())
    platform.add_task(running_task())
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=observation(WorkloadState.READY),
    )

    async with resume_harness(platform, driver=driver) as kit:
        await kit.reconciliation.run()

    assert platform.tasks[TASK_ID]["status"] == "done"
    assert driver.remove_calls == []
    assert driver.sweep_calls == [{str(platform.deployments[DEPLOYMENT_ID]["artifact_id"])}]
