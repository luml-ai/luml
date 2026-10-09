import itertools

from luml_satellite import DeploymentStatus
from luml_satellite.workload import (
    HEALTH_CHECK_FAILED_REASON,
    HEALTH_CHECK_TIMEOUT_REASON,
    NOT_FOUND_REASON,
    RECOVERING_REASON,
    RELAUNCH_FAILED_REASON,
    WORKLOAD_STOPPED_REASON,
    status_transition_allowed,
)


def test_every_allowed_and_forbidden_status_transition() -> None:
    expected = {
        (DeploymentStatus.PENDING, DeploymentStatus.ACTIVE),
        (DeploymentStatus.PENDING, DeploymentStatus.FAILED),
        (DeploymentStatus.PENDING, DeploymentStatus.NOT_RESPONDING),
        (DeploymentStatus.ACTIVE, DeploymentStatus.ACTIVE),
        (DeploymentStatus.ACTIVE, DeploymentStatus.NOT_RESPONDING),
        (DeploymentStatus.NOT_RESPONDING, DeploymentStatus.ACTIVE),
        (DeploymentStatus.NOT_RESPONDING, DeploymentStatus.NOT_RESPONDING),
        (DeploymentStatus.FAILED, DeploymentStatus.ACTIVE),
        (DeploymentStatus.FAILED, DeploymentStatus.FAILED),
        (DeploymentStatus.FAILED, DeploymentStatus.NOT_RESPONDING),
        (DeploymentStatus.DELETION_PENDING, DeploymentStatus.DELETION_FAILED),
        (DeploymentStatus.DELETION_FAILED, DeploymentStatus.DELETION_FAILED),
    }

    for current, target in itertools.product(DeploymentStatus, repeat=2):
        assert status_transition_allowed(current, target) is ((current, target) in expected)

    assert not status_transition_allowed("future-status", DeploymentStatus.ACTIVE)
    assert not status_transition_allowed(DeploymentStatus.ACTIVE, "future-status")


def test_status_reason_strings_are_stable() -> None:
    assert RECOVERING_REASON == "Recovering"
    assert HEALTH_CHECK_FAILED_REASON == "Health check failed"
    assert NOT_FOUND_REASON == "Not Found"
    assert RELAUNCH_FAILED_REASON == "Relaunched container did not become healthy"
    assert HEALTH_CHECK_TIMEOUT_REASON == "healthcheck timeout"
    assert WORKLOAD_STOPPED_REASON == "Container stopped or not found"
