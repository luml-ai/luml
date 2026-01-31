"""Tests for PeriodicController."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from luml_satellite_sdk import PeriodicController
from luml_satellite_sdk.schemas import SatelliteTaskStatus


class MockPlatformClient:
    """Mock platform client for testing."""

    def __init__(self) -> None:
        self.list_tasks = AsyncMock(return_value=[])
        self.update_task_status = AsyncMock()


class TestPeriodicControllerInit:
    """Tests for PeriodicController initialization."""

    def test_init_sets_platform(self) -> None:
        """Test that platform client is set."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        assert controller.platform is platform

    def test_init_sets_dispatch(self) -> None:
        """Test that dispatch callback is set."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        assert controller.dispatch is dispatch

    def test_init_sets_poll_interval(self) -> None:
        """Test that poll interval is set."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=10.0,
        )

        assert controller.poll_interval_s == 10.0

    def test_init_not_stopped(self) -> None:
        """Test that controller starts in non-stopped state."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        assert controller._stopped is False


class TestPeriodicControllerStop:
    """Tests for PeriodicController stop method."""

    def test_stop_sets_stopped_flag(self) -> None:
        """Test that stop sets the stopped flag."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        controller.stop()

        assert controller._stopped is True


class TestPeriodicControllerTick:
    """Tests for PeriodicController tick method."""

    @pytest.mark.asyncio
    async def test_tick_fetches_pending_tasks(self) -> None:
        """Test that tick fetches pending tasks."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        await controller.tick()

        platform.list_tasks.assert_called_once_with(SatelliteTaskStatus.PENDING)

    @pytest.mark.asyncio
    async def test_tick_dispatches_each_task(self) -> None:
        """Test that tick dispatches each fetched task."""
        platform = MockPlatformClient()
        platform.list_tasks.return_value = [
            {"id": "task-1", "type": "deploy"},
            {"id": "task-2", "type": "undeploy"},
        ]
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        await controller.tick()

        assert dispatch.call_count == 2
        dispatch.assert_any_call({"id": "task-1", "type": "deploy"})
        dispatch.assert_any_call({"id": "task-2", "type": "undeploy"})

    @pytest.mark.asyncio
    async def test_tick_no_dispatch_when_no_tasks(self) -> None:
        """Test that tick does not dispatch when no tasks."""
        platform = MockPlatformClient()
        platform.list_tasks.return_value = []
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        await controller.tick()

        dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_tick_handles_dispatch_error(self) -> None:
        """Test that tick handles dispatch errors and updates task status."""
        platform = MockPlatformClient()
        platform.list_tasks.return_value = [{"id": "task-1", "type": "deploy"}]
        dispatch = AsyncMock(side_effect=Exception("Dispatch failed"))

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        await controller.tick()

        platform.update_task_status.assert_called_once_with(
            "task-1",
            SatelliteTaskStatus.FAILED,
            {"reason": "handler error: Dispatch failed"},
        )

    @pytest.mark.asyncio
    async def test_tick_continues_after_dispatch_error(self) -> None:
        """Test that tick continues processing after a dispatch error."""
        platform = MockPlatformClient()
        platform.list_tasks.return_value = [
            {"id": "task-1", "type": "deploy"},
            {"id": "task-2", "type": "undeploy"},
        ]
        # First call fails, second succeeds
        dispatch = AsyncMock(side_effect=[Exception("Failed"), None])

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=5.0,
        )

        await controller.tick()

        assert dispatch.call_count == 2


class TestPeriodicControllerRunForever:
    """Tests for PeriodicController run_forever method."""

    @pytest.mark.asyncio
    async def test_run_forever_stops_when_stopped(self) -> None:
        """Test that run_forever stops when stop() is called."""
        platform = MockPlatformClient()
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=0.01,  # Short interval for testing
        )

        # Stop after first tick
        async def stop_after_tick() -> None:
            await asyncio.sleep(0.02)
            controller.stop()

        await asyncio.gather(controller.run_forever(), stop_after_tick())

        # Should have called tick at least once
        assert platform.list_tasks.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_forever_continues_on_tick_error(self) -> None:
        """Test that run_forever continues after tick errors."""
        platform = MockPlatformClient()
        # First call raises, then returns empty
        call_count = 0

        async def list_tasks_side_effect(
            status: SatelliteTaskStatus,
        ) -> list[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return []

        platform.list_tasks.side_effect = list_tasks_side_effect
        dispatch = AsyncMock()

        controller = PeriodicController(
            platform=platform,  # type: ignore[arg-type]
            dispatch=dispatch,
            poll_interval_s=0.01,
        )

        async def stop_after_ticks() -> None:
            await asyncio.sleep(0.05)
            controller.stop()

        await asyncio.gather(controller.run_forever(), stop_after_ticks())

        # Should have called list_tasks multiple times despite first error
        assert platform.list_tasks.call_count >= 2
