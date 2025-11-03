from typing import Any

from .clients import PlatformClient
from .settings import config


class SatelliteManager:
    def __init__(self, platform: PlatformClient) -> None:
        self.platform = platform

    async def pair(self) -> None:
        await self.platform.pair_satellite(config.BASE_URL.rstrip("/"), self.get_capabilities())

    @staticmethod
    def get_capabilities() -> dict[str, Any]:
        return {"deploy": {"max_concurrency": 2, "labels": ["docker", "demo"]}}
