import logging

from agent.handlers.handler_instances import ms_handler
from agent.schemas import DeploymentUpdate, SatelliteQueueTask, SatelliteTaskStatus
from agent.tasks.base import Task

logger = logging.getLogger(__name__)


class UndeployTask(Task):
    async def run(self, task: SatelliteQueueTask) -> None:
        await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        payload = task.payload or {}
        deployment_id = payload.get("deployment_id")

        try:
            container_removed, model_id = await self.docker.remove_model_container(
                deployment_id=deployment_id
            )
        except Exception as error:
            error_message = {
                "reason": "failed to remove container",
                "error": str(error),
            }
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, error_message
            )
            await self.platform.update_deployment(
                deployment_id, DeploymentUpdate(error_message=error_message)
            )
            return

        try:
            await self.platform.delete_deployment(deployment_id)
        except Exception as error:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                {
                    "reason": "failed to mark deployment deleted",
                    "error": str(error),
                },
            )
            return

        await ms_handler.remove_deployment(deployment_id)

        # if model_id:
        #     try:
        #         await self.docker.cleanup_model_cache(model_id)
        #     except Exception as error:
        #         logger.error(
        #             f"[UndeployTask] Failed to clean model '{model_id}' cache.\n{str(error)}"
        #         )

        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"container_removed": container_removed},
        )
