from abc import ABC, abstractmethod

from agent.clients import DockerService, PlatformClient
from agent.schemas import SatelliteQueueTask


class Task(ABC):
    def __init__(self, *, platform: PlatformClient, docker: DockerService) -> None:
        self.platform = platform
        self.docker = docker

    @abstractmethod
    async def run(self, task: SatelliteQueueTask) -> None: ...
