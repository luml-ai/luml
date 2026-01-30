"""Satellite manager for handling pairing and capability registration."""

from __future__ import annotations

import logging
from typing import Any

from luml_satellite_sdk.client import BasePlatformClient

logger = logging.getLogger("satellite")


class SatelliteManager:
    """Manages satellite pairing and capability registration with the LUML platform.

    This class handles the communication with the LUML backend for registering
    a satellite and its capabilities with an orbit.

    Usage:
        async with PlatformClient(base_url, token) as platform:
            manager = SatelliteManager(platform)
            manager.register_capabilities([
                {
                    "deploy": {
                        "version": 1,
                        "supported_variants": ["pyfunc", "pipeline"],
                    }
                }
            ])
            await manager.pair(base_url="http://localhost:8000", slug="my-satellite")
    """

    def __init__(self, platform: BasePlatformClient) -> None:
        """Initialize the satellite manager.

        Args:
            platform: The platform client for API communication.
        """
        self.platform = platform
        self._capabilities: dict[str, Any] = {}

    def register_capabilities(self, capabilities: list[dict[str, Any]]) -> None:
        """Register capabilities that this satellite supports.

        Each capability should be a dictionary with a capability name as key
        and its configuration as value. Multiple calls will merge capabilities.

        Args:
            capabilities: List of capability dictionaries to register.

        Example:
            manager.register_capabilities([
                {
                    "deploy": {
                        "version": 1,
                        "supported_variants": ["pyfunc"],
                    }
                },
                {
                    "inference": {
                        "version": 1,
                        "max_batch_size": 32,
                    }
                }
            ])
        """
        for capability in capabilities:
            self._capabilities.update(capability)
        logger.debug("Registered capabilities: %s", list(self._capabilities.keys()))

    def get_capabilities(self) -> dict[str, Any]:
        """Get the currently registered capabilities.

        Returns:
            Dictionary of registered capabilities.
        """
        return self._capabilities.copy()

    async def pair(self, base_url: str, slug: str | None = None) -> dict[str, Any]:
        """Pair the satellite with the LUML platform.

        This registers the satellite with the platform, providing its
        base URL and capabilities so the platform knows how to communicate
        with this satellite and what tasks it can handle.

        Args:
            base_url: The base URL where this satellite can be reached.
            slug: Optional unique identifier/slug for this satellite.

        Returns:
            Pairing response data from the platform.

        Raises:
            Exception: If the pairing request fails.
        """
        logger.info(
            "Pairing satellite with platform (base_url=%s, slug=%s)",
            base_url,
            slug,
        )
        result = await self.platform.pair_satellite(
            base_url.rstrip("/"),
            self._capabilities,
            slug,
        )
        logger.info("Satellite paired successfully")
        return result
