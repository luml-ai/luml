"""Tests for SatelliteManager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from luml_satellite_sdk import SatelliteManager


class MockPlatformClient:
    """Mock platform client for testing."""

    def __init__(self) -> None:
        self.pair_satellite = AsyncMock(return_value={"paired": True})


class TestSatelliteManagerInit:
    """Tests for SatelliteManager initialization."""

    def test_init_sets_platform(self) -> None:
        """Test that platform client is set."""
        platform = MockPlatformClient()

        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        assert manager.platform is platform

    def test_init_empty_capabilities(self) -> None:
        """Test that capabilities start empty."""
        platform = MockPlatformClient()

        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        assert manager._capabilities == {}


class TestSatelliteManagerRegisterCapabilities:
    """Tests for SatelliteManager register_capabilities method."""

    def test_register_single_capability(self) -> None:
        """Test registering a single capability."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        manager.register_capabilities([{"deploy": {"version": 1}}])

        assert manager._capabilities == {"deploy": {"version": 1}}

    def test_register_multiple_capabilities(self) -> None:
        """Test registering multiple capabilities at once."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        manager.register_capabilities(
            [
                {"deploy": {"version": 1}},
                {"inference": {"max_batch_size": 32}},
            ]
        )

        assert manager._capabilities == {
            "deploy": {"version": 1},
            "inference": {"max_batch_size": 32},
        }

    def test_register_capabilities_merges(self) -> None:
        """Test that multiple register calls merge capabilities."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        manager.register_capabilities([{"deploy": {"version": 1}}])
        manager.register_capabilities([{"inference": {"version": 1}}])

        assert manager._capabilities == {
            "deploy": {"version": 1},
            "inference": {"version": 1},
        }

    def test_register_capabilities_updates_existing(self) -> None:
        """Test that registering same capability updates it."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        manager.register_capabilities([{"deploy": {"version": 1}}])
        manager.register_capabilities([{"deploy": {"version": 2}}])

        assert manager._capabilities == {"deploy": {"version": 2}}


class TestSatelliteManagerGetCapabilities:
    """Tests for SatelliteManager get_capabilities method."""

    def test_get_capabilities_returns_copy(self) -> None:
        """Test that get_capabilities returns a copy."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]
        manager.register_capabilities([{"deploy": {"version": 1}}])

        capabilities = manager.get_capabilities()

        # Modify returned dict
        capabilities["new"] = "value"

        # Original should be unchanged
        assert "new" not in manager._capabilities

    def test_get_capabilities_empty(self) -> None:
        """Test getting capabilities when none registered."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        capabilities = manager.get_capabilities()

        assert capabilities == {}


class TestSatelliteManagerPair:
    """Tests for SatelliteManager pair method."""

    @pytest.mark.asyncio
    async def test_pair_calls_platform(self) -> None:
        """Test that pair calls platform pair_satellite."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]
        manager.register_capabilities([{"deploy": {"version": 1}}])

        await manager.pair(base_url="http://localhost:8000", slug="my-satellite")

        platform.pair_satellite.assert_called_once_with(
            "http://localhost:8000",
            {"deploy": {"version": 1}},
            "my-satellite",
        )

    @pytest.mark.asyncio
    async def test_pair_strips_trailing_slash(self) -> None:
        """Test that pair strips trailing slash from base_url."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        await manager.pair(base_url="http://localhost:8000/", slug=None)

        call_args = platform.pair_satellite.call_args[0]
        assert call_args[0] == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_pair_returns_response(self) -> None:
        """Test that pair returns the platform response."""
        platform = MockPlatformClient()
        platform.pair_satellite.return_value = {
            "satellite_id": "sat-123",
            "paired": True,
        }
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        result = await manager.pair(base_url="http://localhost:8000")

        assert result == {"satellite_id": "sat-123", "paired": True}

    @pytest.mark.asyncio
    async def test_pair_without_slug(self) -> None:
        """Test pairing without a slug."""
        platform = MockPlatformClient()
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        await manager.pair(base_url="http://localhost:8000")

        platform.pair_satellite.assert_called_once_with(
            "http://localhost:8000",
            {},
            None,
        )

    @pytest.mark.asyncio
    async def test_pair_propagates_error(self) -> None:
        """Test that pair propagates platform errors."""
        platform = MockPlatformClient()
        platform.pair_satellite.side_effect = Exception("Connection failed")
        manager = SatelliteManager(platform=platform)  # type: ignore[arg-type]

        with pytest.raises(Exception, match="Connection failed"):
            await manager.pair(base_url="http://localhost:8000")
