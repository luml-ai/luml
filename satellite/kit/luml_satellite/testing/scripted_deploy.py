from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

from luml_satellite.convergence import WORKLOAD_STOPPED_REASON, PollingPass
from luml_satellite.testing.fake_platform import FakePlatform


@dataclass(frozen=True)
class ScriptedDeployCase:
    deployment_id: str = "10000000-0000-0000-0000-000000000091"
    task_id: str = "20000000-0000-0000-0000-000000000091"
    artifact_id: str = "30000000-0000-0000-0000-000000000091"
    expected_task_statuses: tuple[str, ...] = ("running", "done")
    expected_deployment_statuses: tuple[str, ...] = ("active",)
    expected_reason: str | None = None

    @classmethod
    def workload_dies_before_healthy(cls) -> Self:
        return cls(
            expected_task_statuses=("running", "failed"),
            expected_deployment_statuses=("failed",),
            expected_reason=WORKLOAD_STOPPED_REASON,
        )

    def seed(self, platform: FakePlatform, **deployment_overrides: object) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        deployment: dict[str, Any] = {
            "id": self.deployment_id,
            "orbit_id": platform.orbit_id,
            "satellite_id": platform.satellite_id,
            "satellite_name": "Scripted satellite",
            "orbit_name": "Scripted environment",
            "name": "scripted-deployment",
            "artifact_id": self.artifact_id,
            "artifact_name": "scripted-model.tar.gz",
            "collection_id": "50000000-0000-0000-0000-000000000091",
            "status": "pending",
            "monitoring_mode": "off",
            "satellite_parameters": {},
            "dynamic_attributes_secrets": {},
            "env_variables_secrets": {},
            "env_variables": {},
            "created_at": now,
        }
        deployment.update(deployment_overrides)
        platform.add_deployment(deployment)
        platform.add_task(
            {
                "id": self.task_id,
                "satellite_id": platform.satellite_id,
                "orbit_id": platform.orbit_id,
                "type": "deploy",
                "payload": {"deployment_id": self.deployment_id},
                "status": "pending",
                "scheduled_at": now,
                "created_at": now,
            }
        )
        platform.add_artifact(self.artifact_id, b"scripted artifact")

    async def run_and_assert(self, poller: PollingPass, platform: FakePlatform) -> None:
        for _ in range(10):
            await poller.run()
            await poller.drain()
            if not poller.convergence.in_progress:
                break
        else:
            raise AssertionError("scripted deployment did not settle after ten passes")

        task_statuses = tuple(
            transition.status
            for transition in platform.task_transitions
            if transition.resource_id == self.task_id
        )
        deployment_statuses = tuple(
            transition.status
            for transition in platform.deployment_transitions
            if transition.resource_id == self.deployment_id
        )
        if task_statuses != self.expected_task_statuses:
            raise AssertionError(f"unexpected task status sequence: {task_statuses!r}")
        if deployment_statuses != self.expected_deployment_statuses:
            raise AssertionError(f"unexpected deployment status sequence: {deployment_statuses!r}")
        if self.expected_reason is not None:
            self._assert_failure_reason(platform)

    def _assert_failure_reason(self, platform: FakePlatform) -> None:
        task_result = platform.tasks[self.task_id].get("result")
        deployment_error = platform.deployments[self.deployment_id].get("error_message")
        if not isinstance(task_result, dict) or task_result.get("reason") != self.expected_reason:
            raise AssertionError(f"unexpected task failure result: {task_result!r}")
        if (
            not isinstance(deployment_error, dict)
            or deployment_error.get("reason") != self.expected_reason
        ):
            raise AssertionError(f"unexpected deployment failure: {deployment_error!r}")
