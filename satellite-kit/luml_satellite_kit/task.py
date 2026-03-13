from abc import ABC, abstractmethod

from luml_satellite_kit.schemas.task import SatelliteQueueTask, SatelliteTaskType


class BaseSatelliteTask(ABC):
    task_type: SatelliteTaskType

    @abstractmethod
    async def run(self, task: SatelliteQueueTask) -> None: ...
