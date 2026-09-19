from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    DeploymentSettings,
    DriverError,
    NoServingPlacement,
    PlatformClient,
    PollingPass,
    SatelliteQueueTask,
    TokenDeriver,
    setting_field,
)
from luml_satellite.testing import (
    FakeClock,
    FakeDriver,
    FakeMonitoringBundle,
    FakePlatform,
    FakeServingPlacement,
    ScriptedDeployCase,
    model_description,
)
from luml_satellite.workload import (
    ArtifactDeliveryMode,
    StartResult,
    StartStatus,
    WorkloadObservation,
    WorkloadState,
)
from tests.helpers import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    SECRET_ID,
    TASK_ID,
    deployment_record,
    task_record,
)


@dataclass
class Harness:
    platform: FakePlatform
    client: PlatformClient
    driver: FakeDriver
    serving: FakeServingPlacement | NoServingPlacement
    clock: FakeClock
    convergence: Convergence
    poller: PollingPass


@asynccontextmanager
async def harness(
    platform: FakePlatform,
    *,
    driver: FakeDriver | None = None,
    serving: FakeServingPlacement | NoServingPlacement | None = None,
    monitoring: FakeMonitoringBundle | None = None,
    clock: FakeClock | None = None,
    driver_call_timeout: float = 1.0,
    max_parallel: int = 8,
) -> AsyncIterator[Harness]:
    active_driver = driver or FakeDriver()
    active_serving = serving or FakeServingPlacement()
    active_clock = clock or FakeClock()
    async with PlatformClient(
        "http://platform",
        platform.token,
        transport=platform.transport,
    ) as client:
        resolver = ArtifactResolver(
            client,
            TokenDeriver("satellite-token"),
            satellite_address="http://satellite",
        )
        convergence = Convergence(
            client,
            active_driver,
            resolver,
            serving=active_serving,
            monitoring=monitoring,
            clock=active_clock,
            max_parallel=max_parallel,
            driver_call_timeout=driver_call_timeout,
        )
        yield Harness(
            platform,
            client,
            active_driver,
            active_serving,
            active_clock,
            convergence,
            PollingPass(client, convergence),
        )


def seed_deploy(
    platform: FakePlatform,
    *,
    deployment: dict[str, object] | None = None,
    task: dict[str, object] | None = None,
) -> None:
    platform.add_deployment(deployment_record(**(deployment or {})))
    platform.add_task(task_record(**(task or {})))


def task_failure(platform: FakePlatform, task_id: str = TASK_ID) -> dict[str, object]:
    result = platform.tasks[task_id]["result"]
    assert isinstance(result, dict)
    return result


@pytest.mark.asyncio
async def test_scripted_deploy_case_reaches_the_expected_status_sequence() -> None:
    platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(platform)

    async with harness(platform) as kit:
        await case.run_and_assert(kit.poller, platform)

    record = platform.deployments[case.deployment_id]
    assert record["status"] == "active"
    assert record["inference_url"] == f"/deployments/{case.deployment_id}"


@pytest.mark.asyncio
async def test_scripted_deploy_case_covers_a_workload_dying_before_health() -> None:
    platform = FakePlatform()
    case = ScriptedDeployCase.workload_dies_before_healthy()
    case.seed(platform)
    driver = FakeDriver()
    driver.script_start(case.deployment_id, StartResult(StartStatus.IN_PROGRESS))
    driver.script_observe(
        case.deployment_id,
        WorkloadObservation(WorkloadState.STOPPED, error="process exited"),
    )

    async with harness(platform, driver=driver) as kit:
        await case.run_and_assert(kit.poller, platform)

    assert platform.tasks[case.task_id]["result"]["reason"] == ("Container stopped or not found")
    assert driver.remove_calls == [case.deployment_id]


@pytest.mark.asyncio
async def test_in_progress_deploy_reports_notes_and_finalizes_on_a_later_pass() -> None:
    platform = FakePlatform()
    seed_deploy(platform, deployment={"monitoring_mode": "full"})
    driver = FakeDriver()
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(
            StartStatus.IN_PROGRESS,
            upstream_url="http://model",
            provider_ref="provider-1",
            progress_note="creating",
        ),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(
            WorkloadState.STARTING,
            upstream_url="http://model",
            provider_ref="provider-1",
            progress_note="pulling",
        ),
        WorkloadObservation(
            WorkloadState.READY,
            upstream_url="http://model",
            provider_ref="provider-1",
        ),
    )

    async with harness(
        platform,
        driver=driver,
        monitoring=FakeMonitoringBundle(),
    ) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        assert DEPLOYMENT_ID in kit.convergence.in_progress

        await kit.poller.run()
        assert platform.deployments[DEPLOYMENT_ID]["progress_note"] == "pulling"
        assert platform.deployments[DEPLOYMENT_ID]["status"] == "pending"

        await kit.poller.run()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.deployments[DEPLOYMENT_ID]["provider_ref"] == "provider-1"
    assert platform.deployments[DEPLOYMENT_ID]["progress_note"] is None
    assert platform.deployments[DEPLOYMENT_ID]["monitoring_url"] == (
        f"/deployments/{DEPLOYMENT_ID}/monitoring"
    )
    assert platform.tasks[TASK_ID]["status"] == "done"
    assert platform.tasks[TASK_ID]["result"] == {"inference_url": f"/deployments/{DEPLOYMENT_ID}"}
    assert driver.observe_all_calls == [{DEPLOYMENT_ID}, {DEPLOYMENT_ID}]


@pytest.mark.asyncio
async def test_progress_note_is_truncated_and_a_refused_update_is_tolerated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    platform.script_responses(
        "PATCH",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (422, {"detail": "note refused"}),
    )
    driver = FakeDriver()
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.IN_PROGRESS, progress_note="n" * 1200),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(WorkloadState.READY),
    )

    async with harness(platform, driver=driver) as kit:
        await kit.poller.run()
        await kit.poller.drain()

        assert DEPLOYMENT_ID in kit.convergence.in_progress
        await kit.poller.run()

    note_request = next(
        request
        for request in platform.requests
        if request.method == "PATCH" and isinstance(request.body, dict)
    )
    assert isinstance(note_request.body, dict)
    assert note_request.body["progress_note"] == "n" * 1000
    assert "note refused" in caplog.text
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "healthy"),
    [
        (WorkloadState.STARTING, True),
        (WorkloadState.READY, False),
        (WorkloadState.UNKNOWN, True),
    ],
)
async def test_waiting_states_fail_at_one_deadline_and_clean_up(
    state: WorkloadState,
    healthy: bool,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform, deployment={"satellite_parameters": {"health_check_timeout": 60}})
    driver = FakeDriver()
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.IN_PROGRESS, progress_note="booting"),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(state, recent_logs="x" * 1200),
    )
    serving = FakeServingPlacement()
    serving.script_health(DEPLOYMENT_ID, healthy)
    clock = FakeClock()

    async with harness(platform, driver=driver, serving=serving, clock=clock) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        clock.now = 61
        await kit.poller.run()

        assert DEPLOYMENT_ID not in kit.convergence.in_progress

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "failed"
    assert platform.deployments[DEPLOYMENT_ID]["progress_note"] is None
    error = platform.deployments[DEPLOYMENT_ID]["error_message"]
    assert isinstance(error, dict)
    assert error["reason"] == "healthcheck timeout"
    assert str(error["error"]).endswith("x" * 1000)
    assert "x" * 1001 not in str(error["error"])
    assert driver.remove_calls == [DEPLOYMENT_ID]
    assert serving.unregister_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [WorkloadState.STOPPED, WorkloadState.MISSING, WorkloadState.FAILED],
)
async def test_settled_failure_states_fail_immediately_with_logs(
    state: WorkloadState,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(StartStatus.IN_PROGRESS, progress_note="booting"),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(
            state,
            error="workload exited",
            recent_logs="last log line",
        ),
    )

    async with harness(platform, driver=driver) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        await kit.poller.run()

    failure = task_failure(platform)
    assert failure["reason"] == "Container stopped or not found"
    assert "workload exited" in str(failure["error"])
    assert "last log line" in str(failure["error"])
    assert platform.deployments[DEPLOYMENT_ID]["progress_note"] is None
    assert driver.remove_calls == [DEPLOYMENT_ID]


class GpuSettings(DeploymentSettings):
    gpu_count: int = setting_field(ge=1)


@pytest.mark.asyncio
async def test_invalid_settings_fail_before_start() -> None:
    platform = FakePlatform()
    seed_deploy(platform, deployment={"satellite_parameters": {"gpu_count": "many"}})
    driver = FakeDriver()
    driver.settings_type = GpuSettings
    serving = FakeServingPlacement()

    async with harness(platform, driver=driver, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert driver.start_calls == []
    assert driver.remove_calls == []
    assert serving.unregister_calls == []
    assert task_failure(platform)["reason"] == "Invalid deployment settings"
    assert "gpu_count" in str(task_failure(platform)["error"])


@pytest.mark.asyncio
async def test_unreadable_secret_fails_before_start_and_names_the_variable() -> None:
    platform = FakePlatform()
    seed_deploy(platform, deployment={"env_variables_secrets": {"DATABASE_URL": SECRET_ID}})
    driver = FakeDriver()
    serving = FakeServingPlacement()

    async with harness(platform, driver=driver, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert driver.start_calls == []
    assert driver.remove_calls == []
    assert serving.unregister_calls == []
    assert task_failure(platform)["reason"] == "Secret unavailable"
    assert "DATABASE_URL" in str(task_failure(platform)["error"])


@pytest.mark.asyncio
async def test_unavailable_artifact_fails_before_start() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.artifact_delivery = ArtifactDeliveryMode.PRESIGNED_LINK
    serving = FakeServingPlacement()

    async with harness(platform, driver=driver, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert driver.start_calls == []
    assert driver.remove_calls == []
    assert serving.unregister_calls == []
    assert task_failure(platform)["reason"] == "Artifact unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step", "expected_reason"),
    [
        (StartResult(StartStatus.FAILED, error="provider failed"), "Failed to create container"),
        (
            StartResult(StartStatus.FAILED, error="quota", reason="Provider quota exceeded"),
            "Provider quota exceeded",
        ),
        (RuntimeError("driver exploded"), "Failed to create container"),
        (DriverError("bad image", reason="Image rejected"), "Image rejected"),
    ],
)
async def test_start_failures_use_fixed_or_driver_supplied_reasons_and_clean_up(
    step: StartResult | Exception,
    expected_reason: str,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.script_start(DEPLOYMENT_ID, step)
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(WorkloadState.FAILED, recent_logs="l" * 1200),
    )

    async with harness(platform, driver=driver) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    failure = task_failure(platform)
    assert failure["reason"] == expected_reason
    assert str(failure["error"]).endswith("l" * 1000)
    assert driver.remove_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_finalize_strips_secret_attributes_and_keeps_unreadable_parts_as_none() -> None:
    platform = FakePlatform()
    seed_deploy(
        platform,
        deployment={"dynamic_attributes_secrets": {"password": SECRET_ID}},
    )
    serving = FakeServingPlacement()
    serving.script_description(
        DEPLOYMENT_ID,
        model_description(
            manifest={"name": "model"},
            schema={
                "components": {
                    "schemas": {
                        "DynamicAttributesModel": {
                            "properties": {"password": {"type": "string"}, "safe": {}}
                        }
                    }
                }
            },
            reference_profile=None,
        ),
    )

    async with harness(platform, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    schema = platform.deployments[DEPLOYMENT_ID]["schemas"]
    assert isinstance(schema, dict)
    properties = schema["components"]["schemas"]["DynamicAttributesModel"]["properties"]
    assert properties == {"safe": {}}
    registration = serving.register_calls[0]
    assert registration.description.reference_profile is None
    assert registration.description.manifest == {"name": "model"}


@pytest.mark.asyncio
async def test_an_unreadable_description_does_not_fail_finalize() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    serving = FakeServingPlacement()
    serving.script_description(DEPLOYMENT_ID, RuntimeError("schema unavailable"))

    async with harness(platform, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.deployments[DEPLOYMENT_ID]["schemas"] is None
    assert serving.register_calls[0].description == model_description()


@pytest.mark.asyncio
async def test_registration_failure_fails_finalize_and_removes_the_workload() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    serving = FakeServingPlacement()
    serving.register_error = RuntimeError("registry unavailable")

    async with harness(platform, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert task_failure(platform)["reason"] == "failed to finalize deployment"
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "failed"
    assert kit.driver.remove_calls == [DEPLOYMENT_ID]
    assert serving.unregister_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_active_patch_failure_fails_finalize_and_cleans_up() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    platform.script_responses(
        "PATCH",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (500, {"detail": "write failed"}),
    )

    async with harness(platform) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert task_failure(platform)["reason"] == "failed to finalize deployment"
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "failed"
    assert kit.driver.remove_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_failure_after_active_patch_keeps_the_record_and_workload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    platform.script_responses(
        "POST",
        f"/satellites/v1/tasks/{TASK_ID}/status",
        None,
        (500, {"detail": "done write failed"}),
    )

    async with harness(platform) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.tasks[TASK_ID]["status"] == "running"
    assert kit.driver.remove_calls == []
    assert "became active" in caplog.text


@pytest.mark.asyncio
async def test_kit_refuses_an_illegal_final_transition_and_supersedes_the_task(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    driver.script_observe(DEPLOYMENT_ID, WorkloadObservation(WorkloadState.READY))

    async with harness(platform, driver=driver) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        platform.deployments[DEPLOYMENT_ID]["status"] = "deletion_pending"
        await kit.poller.run()

    assert not any(item.status == "active" for item in platform.deployment_transitions)
    assert task_failure(platform)["reason"] == "superseded by undeploy"
    assert driver.remove_calls == []
    assert "deletion_pending -> active" in caplog.text


@pytest.mark.asyncio
async def test_platform_refusal_of_active_transition_fails_finalize() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    platform.refused_deployment_transitions.add(("pending", "active"))

    async with harness(platform) as kit:
        await kit.poller.run()
        await kit.poller.drain()

    assert task_failure(platform)["reason"] == "failed to finalize deployment"
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "failed"
    assert kit.driver.remove_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_deleted_record_drops_convergence_and_cleans_up() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    driver.script_observe(DEPLOYMENT_ID, WorkloadObservation(WorkloadState.READY))
    serving = FakeServingPlacement()

    async with harness(platform, driver=driver, serving=serving) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        del platform.deployments[DEPLOYMENT_ID]
        await kit.poller.run()

    assert task_failure(platform)["reason"] == "deployment record gone"
    assert driver.remove_calls == [DEPLOYMENT_ID]
    assert serving.unregister_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_failed_reread_still_attempts_the_active_patch() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    driver = FakeDriver()
    driver.script_start(DEPLOYMENT_ID, StartResult(StartStatus.IN_PROGRESS))
    driver.script_observe(DEPLOYMENT_ID, WorkloadObservation(WorkloadState.READY))

    async with harness(platform, driver=driver) as kit:
        await kit.poller.run()
        await kit.poller.drain()
        platform.script_responses(
            "GET",
            f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
            (500, {"detail": "reread failed"}),
        )
        await kit.poller.run()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert platform.tasks[TASK_ID]["status"] == "done"


@pytest.mark.asyncio
async def test_provider_driver_converges_directly_with_no_serving_placement() -> None:
    platform = FakePlatform()
    seed_deploy(platform)
    platform.add_artifact(ARTIFACT_ID, b"artifact")
    driver = FakeDriver(workload_listing=False)
    driver.artifact_delivery = ArtifactDeliveryMode.PRESIGNED_LINK
    driver.script_start(
        DEPLOYMENT_ID,
        StartResult(
            StartStatus.IN_PROGRESS,
            provider_ref="job-123",
            serving_address="https://provider.example/models/fixture",
        ),
    )
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(WorkloadState.READY, provider_ref="job-123"),
    )

    async with harness(platform, driver=driver, serving=NoServingPlacement()) as kit:
        task = await kit.client.list_tasks("pending")
        await kit.convergence.handle_task(SatelliteQueueTask.model_validate(task[0]))
        await kit.convergence.revisit_in_progress()

    record = platform.deployments[DEPLOYMENT_ID]
    assert record["status"] == "active"
    assert record["inference_url"] == "https://provider.example/models/fixture"
    assert record["provider_ref"] == "job-123"
