"""Tests for TaskHandler."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from luml_satellite_sdk import TaskHandler
from luml_satellite_sdk.handler import TaskProtocol
from luml_satellite_sdk.schemas import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)


class MockTaskHandler:
    """Mock task handler implementing TaskProtocol."""

    def __init__(self) -> None:
        self.run = AsyncMock()


class MockPlatformClient:
    """Mock platform client for testing."""

    def __init__(self) -> None:
        self.update_task_status = AsyncMock()


class TestTaskHandlerInit:
    """Tests for TaskHandler initialization."""

    def test_init_sets_platform(self) -> None:
        """Test that platform client is set."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        assert handler.platform is platform

    def test_init_sets_registry(self) -> None:
        """Test that task registry is set."""
        platform = MockPlatformClient()
        mock_task = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: mock_task,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        assert handler._handlers == registry


class TestTaskHandlerDispatch:
    """Tests for TaskHandler dispatch method."""

    @pytest.mark.asyncio
    async def test_dispatch_validates_task(
        self, sample_task_dict: dict[str, Any]
    ) -> None:
        """Test that dispatch validates the task."""
        platform = MockPlatformClient()
        mock_task = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: mock_task,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        await handler.dispatch(sample_task_dict)

        mock_task.run.assert_called_once()
        # Verify the task was validated to SatelliteQueueTask
        call_args = mock_task.run.call_args[0][0]
        assert isinstance(call_args, SatelliteQueueTask)

    @pytest.mark.asyncio
    async def test_dispatch_calls_correct_handler(self) -> None:
        """Test that dispatch calls the correct handler for task type."""
        platform = MockPlatformClient()
        deploy_task = MockTaskHandler()
        undeploy_task = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: deploy_task,  # type: ignore[dict-item]
            SatelliteTaskType.UNDEPLOY: undeploy_task,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        await handler.dispatch(
            {
                "id": "task-1",
                "satellite_id": "sat-1",
                "orbit_id": "orbit-1",
                "type": "undeploy",
                "status": "pending",
                "scheduled_at": "2024-01-15T10:00:00Z",
                "created_at": "2024-01-15T09:00:00Z",
            }
        )

        deploy_task.run.assert_not_called()
        undeploy_task.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_fails_for_invalid_task(self) -> None:
        """Test that dispatch fails for invalid task payload."""
        platform = MockPlatformClient()
        mock_task = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: mock_task,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        # Missing required fields
        await handler.dispatch({"id": "task-1"})

        mock_task.run.assert_not_called()
        platform.update_task_status.assert_called_once_with(
            "task-1",
            SatelliteTaskStatus.FAILED,
            {"reason": "invalid task payload"},
        )

    @pytest.mark.asyncio
    async def test_dispatch_fails_for_unknown_task_type(self) -> None:
        """Test that dispatch fails for unknown task type."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        await handler.dispatch(
            {
                "id": "task-1",
                "satellite_id": "sat-1",
                "orbit_id": "orbit-1",
                "type": "deploy",
                "status": "pending",
                "scheduled_at": "2024-01-15T10:00:00Z",
                "created_at": "2024-01-15T09:00:00Z",
            }
        )

        platform.update_task_status.assert_called_once_with(
            "task-1",
            SatelliteTaskStatus.FAILED,
            {"reason": "unknown type: deploy"},
        )

    @pytest.mark.asyncio
    async def test_dispatch_handles_missing_task_id(self) -> None:
        """Test that dispatch handles missing task id gracefully."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        # Invalid task without id
        await handler.dispatch({"type": "deploy"})

        # Should not try to update status without task id
        platform.update_task_status.assert_not_called()


class TestTaskHandlerRegisterTask:
    """Tests for TaskHandler register_task method."""

    def test_register_task_adds_handler(self) -> None:
        """Test that register_task adds a new handler."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}
        mock_task = MockTaskHandler()

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]
        handler.register_task(SatelliteTaskType.DEPLOY, mock_task)  # type: ignore[arg-type]

        assert handler._handlers[SatelliteTaskType.DEPLOY] is mock_task

    def test_register_task_with_string_type(self) -> None:
        """Test that register_task works with string task types."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}
        mock_task = MockTaskHandler()

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]
        handler.register_task("custom-task", mock_task)  # type: ignore[arg-type]

        assert handler._handlers["custom-task"] is mock_task


class TestTaskHandlerUnregisterTask:
    """Tests for TaskHandler unregister_task method."""

    def test_unregister_task_removes_handler(self) -> None:
        """Test that unregister_task removes the handler."""
        platform = MockPlatformClient()
        mock_task = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: mock_task,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]
        handler.unregister_task(SatelliteTaskType.DEPLOY)

        assert SatelliteTaskType.DEPLOY not in handler._handlers

    def test_unregister_task_raises_key_error(self) -> None:
        """Test that unregister_task raises KeyError for unknown type."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        with pytest.raises(KeyError):
            handler.unregister_task(SatelliteTaskType.DEPLOY)


class TestTaskHandlerRegisteredTypes:
    """Tests for TaskHandler registered_types property."""

    def test_registered_types_returns_list(self) -> None:
        """Test that registered_types returns list of types."""
        platform = MockPlatformClient()
        mock_deploy = MockTaskHandler()
        mock_undeploy = MockTaskHandler()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {
            SatelliteTaskType.DEPLOY: mock_deploy,  # type: ignore[dict-item]
            SatelliteTaskType.UNDEPLOY: mock_undeploy,  # type: ignore[dict-item]
        }

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        types = handler.registered_types

        assert len(types) == 2
        assert SatelliteTaskType.DEPLOY in types
        assert SatelliteTaskType.UNDEPLOY in types

    def test_registered_types_empty_when_no_handlers(self) -> None:
        """Test that registered_types is empty when no handlers."""
        platform = MockPlatformClient()
        registry: dict[SatelliteTaskType | str, TaskProtocol] = {}

        handler = TaskHandler(platform=platform, task_registry=registry)  # type: ignore[arg-type]

        assert handler.registered_types == []
