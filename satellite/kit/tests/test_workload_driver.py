import pytest

from luml_satellite import Deployment
from luml_satellite.testing import (
    DriverConformanceSuite,
    FakeClock,
    FakeDriver,
    FakeSettings,
    fake_artifact_handle,
)
from luml_satellite.workload import (
    RemoveResult,
    StartContext,
    WorkloadObservation,
    WorkloadState,
    wait_until_not_starting,
)
from luml_satellite.workload.recording import RecordingPolicy
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record


@pytest.mark.asyncio
async def test_wait_helper_uses_the_clock_and_returns_the_first_settled_state() -> None:
    driver = FakeDriver()
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(WorkloadState.STARTING),
        WorkloadObservation(WorkloadState.STARTING),
        WorkloadObservation(WorkloadState.READY, upstream_url="http://model"),
    )
    clock = FakeClock(now=10)

    observation = await wait_until_not_starting(
        driver,
        DEPLOYMENT_ID,
        timeout=10,
        poll_interval=2,
        clock=clock,
    )

    assert observation.state is WorkloadState.READY
    assert observation.upstream_url == "http://model"
    assert clock.sleeps == [2, 2]
    assert clock.now == 14


@pytest.mark.asyncio
async def test_wait_helper_stops_exactly_at_the_deadline() -> None:
    driver = FakeDriver()
    driver.script_observe(
        DEPLOYMENT_ID,
        WorkloadObservation(WorkloadState.STARTING),
        WorkloadObservation(WorkloadState.STARTING),
        WorkloadObservation(WorkloadState.STARTING),
    )
    clock = FakeClock()

    with pytest.raises(TimeoutError, match=DEPLOYMENT_ID):
        await wait_until_not_starting(
            driver,
            DEPLOYMENT_ID,
            timeout=3,
            poll_interval=2,
            clock=clock,
        )

    assert clock.sleeps == [2, 1]
    assert clock.now == 3


@pytest.mark.asyncio
async def test_fake_driver_passes_the_conformance_suite() -> None:
    driver = FakeDriver()
    deployment, context = _deployment_and_context()
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=lambda: driver.removal_rechecks,
    )

    await suite.run(deployment, context)

    assert len(driver.start_calls) == 2
    assert driver.supported_tag_combinations is None
    assert driver.removal_rechecks == 1
    assert driver.remove_calls == [DEPLOYMENT_ID]


@pytest.mark.asyncio
async def test_conformance_suite_rejects_unchecked_verified_removal() -> None:
    driver = UnverifiedClaimDriver()
    deployment, context = _deployment_and_context()
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=lambda: driver.removal_rechecks,
    )

    with pytest.raises(AssertionError, match="without a re-check"):
        await suite.run(deployment, context)


@pytest.mark.asyncio
async def test_fake_driver_can_disable_bulk_observation_and_listing() -> None:
    driver = FakeDriver(bulk_observe=False, workload_listing=False)
    deployment, context = _deployment_and_context()
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=lambda: driver.removal_rechecks,
    )

    await suite.run(deployment, context)

    assert driver.observe_all_calls == [{DEPLOYMENT_ID}]


class UnverifiedClaimDriver(FakeDriver):
    async def remove(self, deployment_id: str) -> RemoveResult:
        self.remove_calls.append(deployment_id)
        self._forget(deployment_id)
        return RemoveResult(removed=True, verified=True, artifact_id=ARTIFACT_ID)


def _deployment_and_context() -> tuple[Deployment, StartContext]:
    deployment = Deployment.model_validate(deployment_record())
    settings = FakeSettings(health_check_timeout=30)
    return deployment, StartContext(
        settings=settings,
        secrets={},
        artifact=fake_artifact_handle(ARTIFACT_ID),
        telemetry_endpoint=None,
        health_check_timeout=30,
        recording_policy=RecordingPolicy(),
    )
