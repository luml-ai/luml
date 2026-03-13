from typing import Any

from luml_satellite_kit.clients.platform import PlatformClient


class SatelliteManager:
    def __init__(
        self,
        platform: PlatformClient,
        *,
        capabilities: dict[str, Any],
        slug: str,
        base_url: str,
    ) -> None:
        self.platform = platform
        self.capabilities = capabilities
        self.slug = slug
        self.base_url = base_url

    async def pair(self) -> None:
        await self.platform.pair_satellite(self.base_url.rstrip("/"), self.capabilities, self.slug)
