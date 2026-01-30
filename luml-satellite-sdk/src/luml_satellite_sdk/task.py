"""Base abstractions for LUML Satellite task implementations."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTask(ABC):
    """Abstract base class for satellite task implementations.

    A task represents a unit of work that a satellite can execute.
    Each task type (e.g., deploy, undeploy, inference) should subclass
    this and implement the execute method with its specific logic.

    Tasks are dispatched by the satellite based on their task_type,
    which must match the type field in queued task messages from the platform.
    """

    @abstractmethod
    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the task with the given data.

        Args:
            task_data: Dictionary containing task-specific data from the platform.
                      The structure depends on the task type.

        Returns:
            A dictionary containing the task result. The structure depends
            on the task type but typically includes status and any output data.

        Raises:
            Exception: If the task fails to execute. The satellite should
                      catch this and report the failure to the platform.
        """
        ...

    @classmethod
    @abstractmethod
    def get_task_type(cls) -> str:
        """Return the task type identifier.

        This identifier is used to match incoming task messages from the
        platform to the appropriate task handler.

        Returns:
            A string identifying this task type (e.g., "deploy", "undeploy").
        """
        ...
