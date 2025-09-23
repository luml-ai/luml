from typing import Any

from pydantic import ValidationError

from agent.clients import DockerService, PlatformClient
from agent.schemas import SatelliteQueueTask, SatelliteTaskStatus, SatelliteTaskType
from agent.tasks import DeployTask, PairingTask, Task


# TODO add task undeploy
class TaskHandler:
    def __init__(self, platform: PlatformClient, docker: DockerService) -> None:
        self.platform = platform
        self.docker = docker
        self._handlers: dict[SatelliteTaskType, Task] = {
            SatelliteTaskType.PAIRING: PairingTask(platform=platform, docker=docker),
            SatelliteTaskType.DEPLOY: DeployTask(platform=platform, docker=docker),
        }

    async def dispatch(self, raw_task: dict[str, Any]) -> None:
        try:
            task = SatelliteQueueTask.model_validate(raw_task)
        except ValidationError:
            try:
                tid = int(raw_task.get("id"))
                await self.platform.update_task_status(
                    tid, SatelliteTaskStatus.FAILED, {"reason": "invalid task payload"}
                )
            except Exception:
                pass
            return

        handler = self._handlers.get(task.type)
        if handler is None:
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, {"reason": f"unknown type: {task.type}"}
            )
            return

        await handler.run(task)
