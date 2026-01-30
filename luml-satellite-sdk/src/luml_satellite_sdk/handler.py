"""Task handler and dispatch logic for LUML Satellite SDK.

This module provides the TaskHandler class that manages task registration
and dispatch for satellite workers. Satellites configure the handler with
their task type mappings, and the handler dispatches incoming tasks to
the appropriate registered handlers.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import ValidationError

from luml_satellite_sdk.schemas import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

if TYPE_CHECKING:
    from luml_satellite_sdk.client import BasePlatformClient

logger = logging.getLogger("satellite")


@runtime_checkable
class TaskProtocol(Protocol):
    """Protocol defining the interface for task handlers.

    Task implementations must provide a run method that executes
    the task logic for a given queued task.
    """

    async def run(self, task: SatelliteQueueTask) -> None:
        """Execute the task.

        Args:
            task: The validated task from the platform queue.
        """
        ...


TaskRegistry = dict[SatelliteTaskType | str, TaskProtocol]


class TaskHandler:
    """Dispatcher for satellite task execution.

    The TaskHandler manages a registry of task type handlers and dispatches
    incoming tasks to the appropriate handler based on the task type.

    Satellites configure the handler by passing a mapping of task types
    to their handler implementations. This allows different satellite
    implementations to register their own task types while sharing
    the common dispatch logic.

    Attributes:
        platform: The platform client for status updates.

    Example:
        ```python
        from luml_satellite_sdk import TaskHandler, SatelliteTaskType

        # Create task handlers
        deploy_task = DeployTask(platform=platform, docker=docker)
        undeploy_task = UndeployTask(platform=platform, docker=docker)

        # Register handlers with the dispatcher
        handler = TaskHandler(
            platform=platform,
            task_registry={
                SatelliteTaskType.DEPLOY: deploy_task,
                SatelliteTaskType.UNDEPLOY: undeploy_task,
            },
        )

        # Dispatch a task from the queue
        await handler.dispatch(raw_task_dict)
        ```
    """

    def __init__(
        self,
        platform: BasePlatformClient,
        task_registry: TaskRegistry,
    ) -> None:
        """Initialize the task handler.

        Args:
            platform: Platform client for communicating task status updates.
            task_registry: Mapping of task types to their handler implementations.
                          Keys can be SatelliteTaskType enum values or strings
                          for custom task types.
        """
        self.platform = platform
        self._handlers: TaskRegistry = task_registry

    async def dispatch(self, raw_task: dict[str, Any]) -> None:
        """Validate and dispatch a task to its registered handler.

        This method:
        1. Validates the raw task data against SatelliteQueueTask schema
        2. Looks up the handler for the task type
        3. Executes the handler's run method

        If validation fails or no handler is registered for the task type,
        the task status is updated to FAILED on the platform.

        Args:
            raw_task: Raw task dictionary from the platform queue.
                     Must contain at minimum 'id' and 'type' fields.
        """
        logger.info(
            f"[dispatch] Processing task: {raw_task.get('id', 'unknown')}"
            f" type: {raw_task.get('type', 'unknown')}"
        )

        try:
            task = SatelliteQueueTask.model_validate(raw_task)

        except ValidationError as e:
            logger.error(f"[dispatch] Task validation failed: {e}")
            task_id = raw_task.get("id")
            if task_id is not None:
                with contextlib.suppress(Exception):
                    await self.platform.update_task_status(
                        str(task_id),
                        SatelliteTaskStatus.FAILED,
                        {"reason": "invalid task payload"},
                    )
            return

        handler = self._handlers.get(task.type)
        if handler is None:
            logger.error(f"[dispatch] Unknown task type: {task.type}")
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                {"reason": f"unknown type: {task.type}"},
            )
            return

        handler_name = handler.__class__.__name__
        logger.info(f"[dispatch] Running task {task.id} with handler {handler_name}")
        await handler.run(task)

    def register_task(
        self,
        task_type: SatelliteTaskType | str,
        handler: TaskProtocol,
    ) -> None:
        """Register a new task handler at runtime.

        This allows dynamic registration of task handlers after
        the TaskHandler has been initialized.

        Args:
            task_type: The task type to register the handler for.
            handler: The handler implementation.
        """
        self._handlers[task_type] = handler

    def unregister_task(self, task_type: SatelliteTaskType | str) -> None:
        """Unregister a task handler.

        Args:
            task_type: The task type to unregister.

        Raises:
            KeyError: If the task type is not registered.
        """
        del self._handlers[task_type]

    @property
    def registered_types(self) -> list[SatelliteTaskType | str]:
        """Get list of registered task types.

        Returns:
            List of task types that have registered handlers.
        """
        return list(self._handlers.keys())
