from collections.abc import Mapping

from luml_satellite.wire import DeploymentStatus

RECOVERING_REASON = "Recovering"
HEALTH_CHECK_FAILED_REASON = "Health check failed"
NOT_FOUND_REASON = "Not Found"
RELAUNCH_FAILED_REASON = "Relaunched container did not become healthy"
HEALTH_CHECK_TIMEOUT_REASON = "healthcheck timeout"
WORKLOAD_STOPPED_REASON = "Container stopped or not found"

ALLOWED_STATUS_TRANSITIONS: Mapping[DeploymentStatus, frozenset[DeploymentStatus]] = {
    DeploymentStatus.PENDING: frozenset(
        {
            DeploymentStatus.ACTIVE,
            DeploymentStatus.FAILED,
            DeploymentStatus.NOT_RESPONDING,
        }
    ),
    DeploymentStatus.ACTIVE: frozenset({DeploymentStatus.ACTIVE, DeploymentStatus.NOT_RESPONDING}),
    DeploymentStatus.NOT_RESPONDING: frozenset(
        {DeploymentStatus.ACTIVE, DeploymentStatus.NOT_RESPONDING}
    ),
    DeploymentStatus.FAILED: frozenset(
        {
            DeploymentStatus.ACTIVE,
            DeploymentStatus.FAILED,
            DeploymentStatus.NOT_RESPONDING,
        }
    ),
    DeploymentStatus.DELETION_PENDING: frozenset({DeploymentStatus.DELETION_FAILED}),
    DeploymentStatus.DELETION_FAILED: frozenset({DeploymentStatus.DELETION_FAILED}),
}


def status_transition_allowed(
    current: DeploymentStatus | str,
    target: DeploymentStatus | str,
) -> bool:
    try:
        current_status = DeploymentStatus(current)
        target_status = DeploymentStatus(target)
    except ValueError:
        return False
    return target_status in ALLOWED_STATUS_TRANSITIONS.get(current_status, frozenset())
