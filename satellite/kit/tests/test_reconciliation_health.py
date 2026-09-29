from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    Deployment,
    ModelDescription,
    PlatformClient,
    PollingPass,
    Reconciliation,
    TokenDeriver,
)
from luml_satellite.testing import FakeClock, FakeDriver, FakePlatform, FakeServingPlacement
from luml_satellite.workload import (
    ArtifactDeliveryMode,
    StartContext,
    StartResult,
    StartStatus,
    WorkloadObservation,
    WorkloadState,
)
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record


@dataclass
class RecoveryHarness:
    platform: FakePlatform
    client: PlatformClient
    driver: FakeDriver
    serving: FakeServingPlacement
    clock: FakeClock
    convergence: Convergence
    polling: PollingPass
    reconciliation: Reconciliation


@asynccontextmanager
async def recovery_harness(
    platform: FakePlatform,
    *,
    driver: FakeDriver | None = None,
    serving: FakeServingPlacement | None = None,
    clock: FakeClock | None = None,
    max_relaunch_attempts: int = 3,
) -> AsyncIterator[RecoveryHarness]:
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
            max_relaunch_attempts=max_relaunch_attempts,
        )
        polling = PollingPass(client, convergence)
        reconciliation = Reconciliation(
            client,
            convergence,
            polling,
            clock=active_clock,
            jitter=lambda ceiling: ceiling,
        )
        yield RecoveryHarness(
            platform,
            client,
            active_driver,
            active_serving,
            active_clock,
            convergence,
            polling,
            reconciliation,
        )


def observed(
    state: WorkloadState,
    *,
    healthy_protocol: bool = True,
    error: str | None = None,
    logs: str = "",
    needs_reapply: bool = False,
) -> WorkloadObservation:
    return WorkloadObservation(
        state,
        upstream_url="http://model",
        error=error,
        recent_logs=logs,
        launcher_protocol="fake-v1" if healthy_protocol else None,
        needs_reapply=needs_reapply,
    )


def seed_active(platform: FakePlatform, **overrides: object) -> None:
    values: dict[str, object] = {
        "status": "active",
        "inference_url": f"/deployments/{DEPLOYMENT_ID}",
    }
    values.update(overrides)
    platform.add_deployment(deployment_record(**values))


def transition_reasons(platform: FakePlatform) -> list[str | None]:
    reasons: list[str | None] = []
    for transition in platform.deployment_transitions:
        error = transition.body.get("error_message")
        reasons.append(error.get("reason") if isinstance(error, dict) else None)
    return reasons


class MarkerCheckingDriver(FakeDriver):
    def __init__(self, platform: FakePlatform) -> None:
        super().__init__()
        self.platform = platform
        self.statuses_at_start: list[str] = []

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        self.statuses_at_start.append(str(self.platform.deployments[str(deployment.id)]["status"]))
        return await super().start(deployment, context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_reason", "starts"),
    [
        (WorkloadState.READY, "Health check failed", 0),
        (WorkloadState.STARTING, "Recovering", 1),
        (WorkloadState.STOPPED, "Recovering", 1),
        (WorkloadState.FAILED, "Recovering", 1),
        (WorkloadState.MISSING, "Not Found", 0),
        (WorkloadState.UNKNOWN, None, 0),
    ],
)
async def test_health_pass_applies_each_nonhealthy_state(
    state: WorkloadState,
    expected_reason: str | None,
    starts: int,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(state))
    if starts:
        driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    serving = FakeServingPlacement()
    if state is WorkloadState.READY:
        serving.script_health(DEPLOYMENT_ID, False)

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()

    assert len(driver.start_calls) == starts
    if expected_reason is None:
        assert platform.deployment_transitions == []
    else:
        assert platform.deployments[DEPLOYMENT_ID]["error_message"]["reason"] == expected_reason


@pytest.mark.asyncio
async def test_health_pass_adopts_an_unregistered_healthy_deployment() -> None:
    platform = FakePlatform()
    seed_active(platform, monitoring_mode="full")
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()

    assert DEPLOYMENT_ID in serving.registered
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_health_pass_leaves_a_registered_healthy_deployment_alone() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        requests_after_adoption = len(platform.requests)
        await kit.convergence.health_pass()

    assert len(serving.register_calls) == 1
    assert len(platform.requests) == requests_after_adoption + 1


@pytest.mark.asyncio
async def test_health_failure_is_reported_only_once() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()
    serving.script_health(DEPLOYMENT_ID, False, False)

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        await kit.convergence.health_pass()

    assert transition_reasons(platform) == ["Health check failed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("through_reconciliation", [False, True])
async def test_missing_workload_is_relaunched_only_with_the_recovery_marker(
    through_reconciliation: bool,
) -> None:
    for marked in (False, True):
        platform = FakePlatform()
        seed_active(
            platform,
            status="not_responding" if marked else "active",
            error_message=({"reason": "Recovering", "error": "interrupted"} if marked else None),
        )
        driver = FakeDriver()
        driver.script_observe(
            DEPLOYMENT_ID,
            observed(WorkloadState.MISSING, healthy_protocol=False),
        )
        driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))

        async with recovery_harness(platform, driver=driver) as kit:
            if through_reconciliation:
                await kit.reconciliation.run()
            else:
                await kit.convergence.health_pass()

        assert len(driver.start_calls) == int(marked)
        expected_reason = "Recovering" if marked else "Not Found"
        assert platform.deployments[DEPLOYMENT_ID]["error_message"]["reason"] == expected_reason


@pytest.mark.asyncio
@pytest.mark.parametrize("through_reconciliation", [False, True])
async def test_relaunch_writes_marker_before_start_and_keeps_serving_registration(
    through_reconciliation: bool,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = MarkerCheckingDriver(platform)
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        driver.script_observe(DEPLOYMENT_ID, observed(WorkloadState.STOPPED))
        driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
        if through_reconciliation:
            await kit.reconciliation.run()
        else:
            await kit.convergence.health_pass()

    assert driver.statuses_at_start == ["not_responding"]
    assert DEPLOYMENT_ID in serving.registered
    assert serving.unregister_calls == []
    assert len(driver.start_calls) == 1


@pytest.mark.asyncio
async def test_failed_marker_write_does_not_touch_workload_or_budget() -> None:
    platform = FakePlatform()
    seed_active(platform)
    platform.script_responses(
        "PATCH",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (500, {"detail": "write unavailable"}),
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {}

    assert driver.start_calls == []
    assert driver.remove_calls == []
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"


@pytest.mark.asyncio
async def test_record_deleted_before_recovery_marker_cleans_up_the_workload() -> None:
    platform = FakePlatform()
    seed_active(platform)
    platform.script_responses(
        "GET",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (404, {"detail": "deployment deleted"}),
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()

    assert driver.start_calls == []
    assert driver.remove_calls == [DEPLOYMENT_ID]
    assert serving.unregister_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_start_failure_keeps_marker_and_counts_one_attempt() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(DEPLOYMENT_ID, RuntimeError("image pull failed"))

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 1}
        assert kit.convergence.in_progress == {}

    record = platform.deployments[DEPLOYMENT_ID]
    assert record["status"] == "not_responding"
    assert record["error_message"]["reason"] == "Recovering"
    assert "image pull failed" in record["error_message"]["error"]
    assert driver.remove_calls == []


@pytest.mark.asyncio
async def test_start_failures_exhaust_the_budget_and_keep_the_marker() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        RuntimeError("failure one"),
        RuntimeError("failure two"),
        RuntimeError("failure three"),
        StartResult(StartStatus.IN_PROGRESS),
    )

    async with recovery_harness(platform, driver=driver) as kit:
        for _ in range(5):
            await kit.convergence.health_pass()

    assert len(driver.start_calls) == 3
    assert driver.remove_calls == []
    final_error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert final_error["reason"] == "Recovering"
    assert "Relaunching has stopped" in final_error["error"]


@pytest.mark.asyncio
async def test_relaunch_preparation_failure_keeps_marker_and_names_the_cause() -> None:
    platform = FakePlatform()
    seed_active(platform, env_variables_secrets={"DATABASE_URL": "missing-secret"})
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 1}

    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert error["reason"] == "Recovering"
    assert "Secret unavailable" in error["error"]
    assert "DATABASE_URL" in error["error"]
    assert driver.start_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment_overrides", "artifact_delivery", "expected_error"),
    [
        (
            {"satellite_parameters": {"health_check_timeout": 0}},
            ArtifactDeliveryMode.ON_DEMAND,
            "Invalid deployment settings",
        ),
        ({}, ArtifactDeliveryMode.PRESIGNED_LINK, "Artifact unavailable"),
    ],
)
async def test_other_relaunch_preparation_failures_keep_the_marker(
    deployment_overrides: dict[str, object],
    artifact_delivery: ArtifactDeliveryMode,
    expected_error: str,
) -> None:
    platform = FakePlatform()
    seed_active(platform, **deployment_overrides)
    driver = FakeDriver()
    driver.artifact_delivery = artifact_delivery
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 1}

    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert error["reason"] == "Recovering"
    assert expected_error in error["error"]
    assert driver.start_calls == []


@pytest.mark.asyncio
async def test_failed_relaunch_start_result_keeps_the_marker() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.FAILED, error="image pull refused"),
    )

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 1}

    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert error["reason"] == "Recovering"
    assert "image pull refused" in error["error"]
    assert driver.remove_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [WorkloadState.STOPPED, WorkloadState.MISSING, WorkloadState.FAILED],
)
async def test_settled_relaunch_entry_records_failure_without_removing_workload(
    state: WorkloadState,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        driver.script_observe(
            DEPLOYMENT_ID,
            observed(state, error="replacement stopped", logs="replacement logs"),
        )
        await kit.convergence.revisit_in_progress()
        assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 1}

    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert error["reason"] == "Relaunched container did not become healthy"
    assert "replacement logs" in error["error"]
    assert driver.remove_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("waiting_state", [WorkloadState.READY, WorkloadState.UNKNOWN])
async def test_waiting_relaunch_entry_fails_at_its_deadline(
    waiting_state: WorkloadState,
) -> None:
    platform = FakePlatform()
    seed_active(platform, satellite_parameters={"health_check_timeout": 1})
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    serving = FakeServingPlacement()
    if waiting_state is WorkloadState.READY:
        serving.script_health(DEPLOYMENT_ID, False)
    clock = FakeClock()

    async with recovery_harness(
        platform,
        driver=driver,
        serving=serving,
        clock=clock,
    ) as kit:
        await kit.convergence.health_pass()
        driver.script_observe(
            DEPLOYMENT_ID,
            observed(waiting_state, error="probe refused", logs="recent output"),
        )
        clock.now = 2
        await kit.convergence.revisit_in_progress()

    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert error["reason"] == "Relaunched container did not become healthy"
    assert "recent output" in error["error"]
    assert driver.remove_calls == []


@pytest.mark.asyncio
async def test_relaunch_budget_stops_after_three_deadline_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    seed_active(platform, satellite_parameters={"health_check_timeout": 1})
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=observed(WorkloadState.STOPPED, logs="old logs"),
    )
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.IN_PROGRESS),
        StartResult(StartStatus.IN_PROGRESS),
        StartResult(StartStatus.IN_PROGRESS),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        observed(WorkloadState.STARTING, logs="attempt one"),
        observed(WorkloadState.STARTING, logs="attempt two"),
        observed(WorkloadState.STARTING, logs="attempt three"),
        observed(WorkloadState.STARTING, logs="attempt four"),
    )
    clock = FakeClock()

    async with recovery_harness(platform, driver=driver, clock=clock) as kit:
        for _ in range(3):
            await kit.convergence.health_pass()
            clock.now += 2
            await kit.convergence.revisit_in_progress()
        await kit.convergence.health_pass()
        transition_count = len(platform.deployment_transitions)
        await kit.convergence.health_pass()

    assert len(driver.start_calls) == 3
    assert driver.remove_calls == []
    assert transition_reasons(platform).count("Recovering") == 3
    assert transition_reasons(platform).count("Relaunched container did not become healthy") == 4
    final_error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert final_error["reason"] == "Relaunched container did not become healthy"
    assert "Relaunching has stopped" in final_error["error"]
    assert "attempt" in final_error["error"]
    assert DEPLOYMENT_ID in caplog.text
    assert len(platform.deployment_transitions) == transition_count


@pytest.mark.asyncio
async def test_successful_relaunch_resets_the_attempt_budget() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        RuntimeError("failure one"),
        RuntimeError("failure two"),
        StartResult(StartStatus.READY, upstream_url="http://model"),
        RuntimeError("later failure one"),
        RuntimeError("later failure two"),
        RuntimeError("later failure three"),
        StartResult(StartStatus.IN_PROGRESS),
    )

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        await kit.convergence.health_pass()
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {}
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
        driver.script_observe(DEPLOYMENT_ID, observed(WorkloadState.STOPPED))
        for _ in range(4):
            await kit.convergence.health_pass()

    assert len(driver.start_calls) == 6
    assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 3}


@pytest.mark.asyncio
async def test_adoption_resets_the_attempt_budget() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        RuntimeError("failure one"),
        RuntimeError("failure two"),
        RuntimeError("later failure one"),
        RuntimeError("later failure two"),
        RuntimeError("later failure three"),
        StartResult(StartStatus.IN_PROGRESS),
    )

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        await kit.convergence.health_pass()
        driver.script_observe(DEPLOYMENT_ID, observed(WorkloadState.READY))
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {}
        driver.script_observe(DEPLOYMENT_ID, observed(WorkloadState.STOPPED))
        for _ in range(4):
            await kit.convergence.health_pass()

    assert len(driver.start_calls) == 5
    assert kit.convergence.relaunch_failures == {DEPLOYMENT_ID: 3}


@pytest.mark.asyncio
async def test_reconciliation_rechecks_unknown_then_health_pass_adopts() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.script_observe(
        DEPLOYMENT_ID,
        observed(WorkloadState.UNKNOWN),
        observed(WorkloadState.UNKNOWN),
        observed(WorkloadState.READY),
    )
    clock = FakeClock()
    serving = FakeServingPlacement()

    async with recovery_harness(
        platform,
        driver=driver,
        clock=clock,
        serving=serving,
    ) as kit:
        await kit.reconciliation.run()
        assert serving.register_calls == []
        assert platform.deployment_transitions == []
        await kit.convergence.health_pass()

    assert clock.sleeps == [15.0]
    assert DEPLOYMENT_ID in serving.registered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_reason", "starts"),
    [
        (WorkloadState.READY, "Health check failed", 0),
        (WorkloadState.STARTING, "Recovering", 1),
        (WorkloadState.STOPPED, "Recovering", 1),
        (WorkloadState.FAILED, "Recovering", 1),
    ],
)
async def test_reconciliation_applies_each_nonhealthy_existing_state(
    state: WorkloadState,
    expected_reason: str,
    starts: int,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(state))
    if starts:
        driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    serving = FakeServingPlacement()
    if state is WorkloadState.READY:
        serving.script_health(DEPLOYMENT_ID, False)

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.reconciliation.run()

    assert len(driver.start_calls) == starts
    assert platform.deployments[DEPLOYMENT_ID]["error_message"]["reason"] == expected_reason


@pytest.mark.asyncio
async def test_reconciliation_relaunches_absent_or_different_protocol() -> None:
    for launcher_protocol in (None, "old-v1"):
        platform = FakePlatform()
        seed_active(platform)
        driver = FakeDriver()
        driver.add_workload(
            DEPLOYMENT_ID,
            observation=WorkloadObservation(
                WorkloadState.READY,
                upstream_url="http://model",
                launcher_protocol=launcher_protocol,
            ),
        )
        driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))

        async with recovery_harness(platform, driver=driver) as kit:
            await kit.reconciliation.run()

        assert len(driver.start_calls) == 1
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "not_responding"


@pytest.mark.asyncio
async def test_matching_protocol_is_adopted_without_relaunch() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.reconciliation.run()

    assert driver.start_calls == []
    assert DEPLOYMENT_ID in serving.registered


@pytest.mark.asyncio
@pytest.mark.parametrize("through_reconciliation", [False, True])
async def test_reapply_is_tracked_without_a_status_change(
    through_reconciliation: bool,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=observed(WorkloadState.READY, needs_reapply=True),
    )
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))

    async with recovery_harness(platform, driver=driver) as kit:
        if through_reconciliation:
            await kit.reconciliation.run()
        else:
            await kit.convergence.health_pass()
        assert kit.convergence.in_progress[DEPLOYMENT_ID].kind == "reapply"
        assert platform.deployment_transitions == []
        driver.script_observe(DEPLOYMENT_ID, observed(WorkloadState.READY))
        await kit.convergence.revisit_in_progress()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.deployment_transitions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_start",
    [
        RuntimeError("apply raised"),
        StartResult(StartStatus.FAILED, error="apply failed"),
    ],
)
async def test_failed_reapply_retries_without_touching_relaunch_budget(
    failed_start: Exception | StartResult,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=observed(WorkloadState.READY, needs_reapply=True),
    )
    driver.script_start(
        DEPLOYMENT_ID,
        failed_start,
        StartResult(StartStatus.IN_PROGRESS),
    )

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.convergence.health_pass()
        await kit.convergence.health_pass()
        assert kit.convergence.relaunch_failures == {}

    assert len(driver.start_calls) == 2
    assert platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_immediately_ready_reapply_is_adopted_without_a_status_change() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(
        DEPLOYMENT_ID,
        observation=observed(WorkloadState.READY, needs_reapply=True),
    )
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.READY, upstream_url="http://model"),
    )
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()

    assert kit.convergence.in_progress == {}
    assert DEPLOYMENT_ID in serving.registered
    assert platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_finalize_failure_without_a_deploy_task_is_retried() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.READY, upstream_url="http://model"),
    )
    serving = FakeServingPlacement()
    serving.register_error = RuntimeError("registry unavailable")

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        assert kit.convergence.in_progress == {}
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "not_responding"
        serving.register_error = None
        await kit.convergence.health_pass()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert DEPLOYMENT_ID in serving.registered


@pytest.mark.asyncio
async def test_relaunch_recording_failure_after_activation_is_retried() -> None:
    platform = FakePlatform()
    seed_active(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.STOPPED))
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.READY, upstream_url="http://model"),
    )
    serving = FakeServingPlacement()
    serving.note_error = RuntimeError("registry unavailable")

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
        serving.note_error = None
        await kit.convergence.health_pass()

    assert len(serving.register_calls) == 2
    assert len(serving.noted_records) == 1


@pytest.mark.asyncio
async def test_adoption_recording_failure_after_activation_is_retried() -> None:
    platform = FakePlatform()
    seed_active(
        platform,
        status="not_responding",
        error_message={"reason": "Health check failed", "error": "probe failed"},
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()
    serving.note_error = RuntimeError("registry unavailable")

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
        serving.note_error = None
        await kit.convergence.health_pass()

    assert len(serving.register_calls) == 2
    assert len(serving.noted_records) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 422, 500])
async def test_active_adoption_update_failure_keeps_serving_and_is_retried(
    status_code: int,
) -> None:
    platform = FakePlatform()
    seed_active(platform)
    platform.script_responses(
        "PATCH",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (status_code, {"detail": "update failed"}),
        None,
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        assert DEPLOYMENT_ID in serving.registered
        assert driver.remove_calls == []
        await kit.convergence.health_pass()

    assert len(serving.register_calls) == 2
    assert len(serving.noted_records) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 422, 500])
async def test_promotion_failure_keeps_serving_and_is_retried(status_code: int) -> None:
    platform = FakePlatform()
    seed_active(
        platform,
        status="not_responding",
        error_message={"reason": "Health check failed", "error": "probe failed"},
    )
    platform.script_responses(
        "PATCH",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (status_code, {"detail": "promotion failed"}),
        None,
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.convergence.health_pass()
        assert DEPLOYMENT_ID in serving.registered
        assert driver.remove_calls == []
        await kit.convergence.health_pass()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert len(serving.register_calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("through_reconciliation", [False, True])
async def test_pass_prefers_one_bulk_observation(through_reconciliation: bool) -> None:
    platform = FakePlatform()
    driver = FakeDriver()
    deployment_ids: set[str] = set()
    for index in range(5):
        deployment_id = f"10000000-0000-0000-0000-{index:012d}"
        deployment_ids.add(deployment_id)
        platform.add_deployment(
            deployment_record(
                id=deployment_id,
                status="active",
                inference_url=f"/deployments/{deployment_id}",
            )
        )
        driver.add_workload(deployment_id, observation=observed(WorkloadState.READY))

    async with recovery_harness(platform, driver=driver) as kit:
        if through_reconciliation:
            await kit.reconciliation.run()
        else:
            await kit.convergence.health_pass()

    assert driver.observe_all_calls == [deployment_ids]


@pytest.mark.asyncio
async def test_orphan_cleanup_removes_only_owned_identified_unshared_workloads() -> None:
    platform = FakePlatform()
    driver = FakeDriver()
    driver.add_workload("owned", artifact_id=ARTIFACT_ID)
    driver.add_workload("shared", owned=True, shared=True)
    driver.add_workload("foreign", owned=False)
    driver.add_unidentified_workload("unidentified", owned=True)

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.reconciliation.run()

    assert driver.remove_calls == ["owned"]
    assert driver.sweep_calls == [set()]


@pytest.mark.asyncio
async def test_orphan_cleanup_is_skipped_when_listing_is_unsupported() -> None:
    platform = FakePlatform()
    driver = FakeDriver(workload_listing=False)
    driver.add_workload("unknown", artifact_id=ARTIFACT_ID)

    async with recovery_harness(platform, driver=driver) as kit:
        await kit.reconciliation.run()

    assert driver.remove_calls == []
    assert driver.sweep_calls == [set()]


@pytest.mark.asyncio
async def test_reconciliation_retries_deployment_listing_before_other_work() -> None:
    platform = FakePlatform()
    seed_active(platform)
    path = "/satellites/v1/deployments"
    platform.script_responses(
        "GET",
        path,
        (503, {"detail": "not ready"}),
        (503, {"detail": "not ready"}),
        None,
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    clock = FakeClock()

    async with recovery_harness(platform, driver=driver, clock=clock) as kit:
        await kit.reconciliation.run()

    assert clock.sleeps == [1.0, 2.0]
    assert DEPLOYMENT_ID in kit.serving.registered


@pytest.mark.asyncio
async def test_description_failure_during_adoption_records_none() -> None:
    platform = FakePlatform()
    seed_active(
        platform,
        status="not_responding",
        error_message={"reason": "Recovering", "error": "interrupted"},
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()
    serving.script_description(DEPLOYMENT_ID, RuntimeError("description unavailable"))

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.reconciliation.run()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    registration = serving.registered[DEPLOYMENT_ID]
    assert registration.description == ModelDescription()
    assert platform.deployments[DEPLOYMENT_ID]["schemas"] is None


@pytest.mark.asyncio
async def test_reconciliation_marker_tracks_ready_but_unhealthy_workload() -> None:
    platform = FakePlatform()
    seed_active(
        platform,
        status="not_responding",
        error_message={"reason": "Recovering", "error": "interrupted"},
    )
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, observation=observed(WorkloadState.READY))
    serving = FakeServingPlacement()
    serving.script_health(DEPLOYMENT_ID, False)

    async with recovery_harness(platform, driver=driver, serving=serving) as kit:
        await kit.reconciliation.run()
        entry = kit.convergence.in_progress[DEPLOYMENT_ID]

    assert entry.kind == "relaunch"
    assert driver.start_calls == []
    assert platform.deployments[DEPLOYMENT_ID]["error_message"]["reason"] == "Recovering"
