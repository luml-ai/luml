import contextlib
import logging
from typing import Any

from pydantic import ValidationError

from luml_satellite_kit.clients.platform import PlatformClient
from luml_satellite_kit.schemas.task import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)
from luml_satellite_kit.task import BaseSatelliteTask

logger = logging.getLogger("satellite")


class TaskDispatcher:
    def __init__(
        self,
        *,
        handlers: dict[SatelliteTaskType, BaseSatelliteTask],
        platform: PlatformClient,
    ) -> None:
        self.handlers = handlers
        self.platform = platform

    async def dispatch(self, raw_task: dict[str, Any]) -> None:
        logger.info(
            f"[dispatch] Processing task: {raw_task.get('id', 'unknown')}"
            f" type: {raw_task.get('type', 'unknown')}"
        )

        try:
            task = SatelliteQueueTask.model_validate(raw_task)
        except ValidationError as e:
            logger.error(f"[dispatch] Task validation failed: {e}")
            with contextlib.suppress(Exception):
                await self.platform.update_task_status(
                    raw_task.get("id"),
                    SatelliteTaskStatus.FAILED,
                    {"reason": "invalid task payload"},
                )
            return

        handler = self.handlers.get(task.type)
        if handler is None:
            logger.error(f"[dispatch] Unknown task type: {task.type}")
            await self.platform.update_task_status(
                task.id, SatelliteTaskStatus.FAILED, {"reason": f"unknown type: {task.type}"}
            )
            return

        logger.info(f"[dispatch] Running task {task.id} with handler {handler.__class__.__name__}")
        await handler.run(task)
