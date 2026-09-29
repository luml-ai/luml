from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    PlatformClient,
    PollingPass,
    TokenDeriver,
)
from luml_satellite.testing import (
    FakeDriver,
    FakeMonitoringBundle,
    FakePlatform,
    FakeServingPlacement,
)
from luml_satellite.workload import RemoveResult
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, TASK_ID, deployment_record, task_record


@asynccontextmanager
async def task_kit(
    platform: FakePlatform,
    *,
    driver: FakeDriver | None = None,
    serving: FakeServingPlacement | None = None,
    monitoring: FakeMonitoringBundle | None = None,
) -> AsyncIterator[tuple[Convergence, PollingPass, FakeDriver, FakeServingPlacement]]:
    active_driver = driver or FakeDriver()
    active_serving = serving or FakeServingPlacement()
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
            monitoring=monitoring,
        )
        yield convergence, PollingPass(client, convergence), active_driver, active_serving


def seed_undeploy(platform: FakePlatform, *, with_deployment: bool = True) -> None:
    if with_deployment:
        platform.add_deployment(deployment_record(status="deletion_pending"))
    platform.add_task(task_record(type="undeploy"))


@pytest.mark.asyncio
async def test_deploy_fetch_failure_has_the_fixed_reason_and_no_cleanup() -> None:
    platform = FakePlatform()
    platform.add_task(task_record())

    async with task_kit(platform) as (_, poller, driver, serving):
        await poller.run()
        await poller.drain()

    assert platform.tasks[TASK_ID]["result"]["reason"] == "failed to get deployment details"
    assert driver.start_calls == []
    assert driver.remove_calls == []
    assert serving.unregister_calls == []


@pytest.mark.asyncio
async def test_undeploy_removes_unregisters_releases_and_reports_truthfully() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, artifact_id=ARTIFACT_ID)
    serving = FakeServingPlacement()

    async with task_kit(platform, driver=driver, serving=serving) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert DEPLOYMENT_ID not in platform.deployments
    assert platform.tasks[TASK_ID]["status"] == "done"
    assert platform.tasks[TASK_ID]["result"] == {"container_removed": True}
    assert driver.release_calls == [(ARTIFACT_ID, False)]
    assert serving.unregister_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_undeploy_keeps_an_artifact_referenced_by_another_deployment() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    other_id = "10000000-0000-0000-0000-000000000099"
    platform.add_deployment(deployment_record(id=other_id, status="active"))
    driver = FakeDriver()
    driver.add_workload(DEPLOYMENT_ID, artifact_id=ARTIFACT_ID)

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert driver.release_calls == [(ARTIFACT_ID, True)]


@pytest.mark.asyncio
async def test_undeploy_rejects_an_unverified_removal_without_deleting_the_record() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    driver = FakeDriver()
    driver.script_remove(
        DEPLOYMENT_ID,
        RemoveResult(removed=True, verified=False, artifact_id=ARTIFACT_ID),
    )

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert DEPLOYMENT_ID in platform.deployments
    assert platform.deployments[DEPLOYMENT_ID]["status"] == "deletion_failed"
    assert platform.tasks[TASK_ID]["result"]["reason"] == "Failed to remove container."
    assert not any(request.method == "DELETE" for request in platform.requests)


@pytest.mark.asyncio
async def test_undeploy_maps_a_remove_exception_to_deletion_failed() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    driver = FakeDriver()
    driver.script_remove(DEPLOYMENT_ID, RuntimeError("provider unavailable"))

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "deletion_failed"
    assert platform.tasks[TASK_ID]["result"] == {
        "reason": "Failed to remove container.",
        "error": "provider unavailable",
    }


@pytest.mark.asyncio
async def test_undeploy_accepts_a_verified_noop_and_reports_removed_false() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    driver = FakeDriver()
    driver.script_remove(
        DEPLOYMENT_ID,
        RemoveResult(removed=False, verified=True, artifact_id=ARTIFACT_ID),
    )

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert DEPLOYMENT_ID not in platform.deployments
    assert platform.tasks[TASK_ID]["result"] == {"container_removed": False}


@pytest.mark.asyncio
async def test_undeploy_treats_an_already_deleted_record_as_success() -> None:
    platform = FakePlatform()
    seed_undeploy(platform, with_deployment=False)
    driver = FakeDriver()
    driver.script_remove(
        DEPLOYMENT_ID,
        RemoveResult(removed=False, verified=True, artifact_id=ARTIFACT_ID),
    )

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert platform.tasks[TASK_ID]["status"] == "done"
    assert platform.tasks[TASK_ID]["result"] == {"container_removed": False}


@pytest.mark.asyncio
async def test_undeploy_delete_failure_marks_the_record_deletion_failed() -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    platform.script_responses(
        "DELETE",
        f"/satellites/v1/deployments/{DEPLOYMENT_ID}",
        (500, {"detail": "database unavailable"}),
    )

    async with task_kit(platform) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert platform.deployments[DEPLOYMENT_ID]["status"] == "deletion_failed"
    assert platform.tasks[TASK_ID]["result"]["reason"] == "Failed to delete deployment."


class ReleaseFailureDriver(FakeDriver):
    async def release_artifact(self, artifact_id: str, still_referenced: bool) -> None:
        self.release_calls.append((artifact_id, still_referenced))
        raise RuntimeError("cache unavailable")


@pytest.mark.asyncio
async def test_artifact_release_failure_does_not_fail_undeploy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform()
    seed_undeploy(platform)
    driver = ReleaseFailureDriver()
    driver.add_workload(DEPLOYMENT_ID, artifact_id=ARTIFACT_ID)

    async with task_kit(platform, driver=driver) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert platform.tasks[TASK_ID]["status"] == "done"
    assert "cache unavailable" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("monitoring_mode", "expected_link", "expected_enabled"),
    [
        ("full", f"/deployments/{DEPLOYMENT_ID}/monitoring", True),
        ("off", None, False),
    ],
)
async def test_reconcile_active_reregisters_serving_and_monitoring(
    monitoring_mode: str,
    expected_link: str | None,
    expected_enabled: bool,
) -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record(status="active", monitoring_mode=monitoring_mode))
    platform.add_task(task_record(type="reconcile"))
    serving = FakeServingPlacement()

    async with task_kit(
        platform,
        serving=serving,
        monitoring=FakeMonitoringBundle(),
    ) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert len(serving.register_calls) == 1
    assert platform.deployments[DEPLOYMENT_ID]["monitoring_url"] == expected_link
    assert platform.tasks[TASK_ID]["result"] == {
        "reconciled": True,
        "monitoring_enabled": expected_enabled,
    }


@pytest.mark.asyncio
async def test_reconcile_inactive_reports_the_current_status_without_registering() -> None:
    platform = FakePlatform()
    platform.add_deployment(deployment_record(status="failed"))
    platform.add_task(task_record(type="reconcile"))
    serving = FakeServingPlacement()

    async with task_kit(platform, serving=serving) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert serving.register_calls == []
    assert platform.tasks[TASK_ID]["result"] == {
        "reconciled": False,
        "reason": "status=failed",
    }


@pytest.mark.asyncio
async def test_reconcile_fetch_and_registration_failures_keep_the_fixed_reasons() -> None:
    fetch_platform = FakePlatform()
    fetch_platform.add_task(task_record(type="reconcile"))

    async with task_kit(fetch_platform) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert fetch_platform.tasks[TASK_ID]["result"]["reason"] == ("Failed to fetch deployment.")

    register_platform = FakePlatform()
    register_platform.add_deployment(deployment_record(status="active"))
    register_platform.add_task(task_record(type="reconcile"))
    serving = FakeServingPlacement()
    serving.register_error = RuntimeError("registry unavailable")

    async with task_kit(register_platform, serving=serving) as (_, poller, _, _):
        await poller.run()
        await poller.drain()

    assert register_platform.tasks[TASK_ID]["result"] == {
        "reason": "Failed to reconcile deployment.",
        "error": "registry unavailable",
    }
