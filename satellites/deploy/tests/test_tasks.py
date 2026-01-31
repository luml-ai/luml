"""Tests for deploy satellite tasks."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luml_satellite_sdk.schemas import (
    SatelliteTaskStatus,
)


class TestDeployTask:
    """Tests for DeployTask."""

    def test_get_task_type(self) -> None:
        """Test that get_task_type returns 'deploy'."""
        from deploy_satellite.tasks import DeployTask

        assert DeployTask.get_task_type() == "deploy"

    def test_init(self, mock_platform_client: MagicMock) -> None:
        """Test DeployTask initialization."""
        from deploy_satellite.tasks import DeployTask

        mock_docker = MagicMock()

        task = DeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
            model_image="test-image:latest",
            model_server_port=9000,
        )

        assert task.platform is mock_platform_client
        assert task.docker is mock_docker
        assert task.model_image == "test-image:latest"
        assert task.model_server_port == 9000

    @pytest.mark.asyncio
    async def test_execute_missing_deployment_id(
        self, mock_platform_client: MagicMock
    ) -> None:
        """Test execute fails when deployment_id is missing."""
        from deploy_satellite.tasks import DeployTask

        mock_docker = MagicMock()

        task = DeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
            model_image="test-image:latest",
        )

        result = await task.execute({"id": "task-123", "payload": {}})

        assert result == {"error": "Missing deployment_id"}
        mock_platform_client.update_task_status.assert_any_call(
            "task-123", SatelliteTaskStatus.RUNNING
        )

    @pytest.mark.asyncio
    async def test_execute_sets_running_status(
        self,
        mock_platform_client: MagicMock,
        sample_deployment: Any,
    ) -> None:
        """Test that execute sets task status to RUNNING."""
        from deploy_satellite.tasks import DeployTask

        mock_docker = MagicMock()
        mock_docker.run_model_container = AsyncMock()
        mock_docker.check_container_running = AsyncMock()

        mock_platform_client.get_deployment.return_value = sample_deployment
        mock_platform_client.get_model_artifact_download_url.return_value = (
            "http://example.com/model.tar"
        )

        task = DeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
            model_image="test-image:latest",
        )

        # Mock health check to fail quickly
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value = mock_client

            # Override default timeout to speed up test
            task.default_health_check_timeout = 1

            await task.execute(
                {"id": "task-123", "payload": {"deployment_id": "dep-001"}}
            )

        # Check that RUNNING status was set
        calls = mock_platform_client.update_task_status.call_args_list
        assert any(
            call[0] == ("task-123", SatelliteTaskStatus.RUNNING) for call in calls
        )

    def test_get_model_id_from_url(self) -> None:
        """Test extracting model ID from URL."""
        from deploy_satellite.tasks import DeployTask

        url = "https://bucket.s3.amazonaws.com/models/my-model.tar?signature=abc"
        model_id = DeployTask._get_model_id_from_url(url)

        # Should return a consistent hash
        assert len(model_id) == 32  # MD5 hex digest length
        assert model_id.isalnum()


class TestUndeployTask:
    """Tests for UndeployTask."""

    def test_get_task_type(self) -> None:
        """Test that get_task_type returns 'undeploy'."""
        from deploy_satellite.tasks import UndeployTask

        assert UndeployTask.get_task_type() == "undeploy"

    def test_init(self, mock_platform_client: MagicMock) -> None:
        """Test UndeployTask initialization."""
        from deploy_satellite.tasks import UndeployTask

        mock_docker = MagicMock()

        task = UndeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
        )

        assert task.platform is mock_platform_client
        assert task.docker is mock_docker

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_platform_client: MagicMock) -> None:
        """Test successful undeploy execution."""
        from deploy_satellite.tasks import UndeployTask

        mock_docker = MagicMock()
        mock_docker.remove_model_container = AsyncMock(return_value=(True, "model-123"))

        task = UndeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
        )

        result = await task.execute(
            {
                "id": "task-456",
                "payload": {"deployment_id": "12345678-1234-5678-1234-567812345678"},
            }
        )

        assert result == {"container_removed": True}
        mock_platform_client.update_task_status.assert_any_call(
            "task-456", SatelliteTaskStatus.RUNNING
        )
        mock_platform_client.delete_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_container_removal_failure(
        self, mock_platform_client: MagicMock
    ) -> None:
        """Test undeploy when container removal fails."""
        from deploy_satellite.tasks import UndeployTask

        mock_docker = MagicMock()
        mock_docker.remove_model_container = AsyncMock(
            side_effect=Exception("Docker error")
        )

        task = UndeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
        )

        result = await task.execute(
            {
                "id": "task-456",
                "payload": {"deployment_id": "12345678-1234-5678-1234-567812345678"},
            }
        )

        assert result == {"error": "Failed to remove container"}
        # Should have updated task status to FAILED
        calls = mock_platform_client.update_task_status.call_args_list
        assert any(call[0][1] == SatelliteTaskStatus.FAILED for call in calls)

    @pytest.mark.asyncio
    async def test_execute_deployment_deletion_failure(
        self, mock_platform_client: MagicMock
    ) -> None:
        """Test undeploy when deployment deletion fails."""
        from deploy_satellite.tasks import UndeployTask

        mock_docker = MagicMock()
        mock_docker.remove_model_container = AsyncMock(return_value=(True, "model-123"))
        mock_platform_client.delete_deployment = AsyncMock(
            side_effect=Exception("API error")
        )

        task = UndeployTask(
            platform=mock_platform_client,
            docker=mock_docker,
        )

        result = await task.execute(
            {
                "id": "task-456",
                "payload": {"deployment_id": "12345678-1234-5678-1234-567812345678"},
            }
        )

        assert result == {"error": "Failed to delete deployment"}


class TestTasksExports:
    """Tests for tasks module exports."""

    def test_deploy_task_exported(self) -> None:
        """Test that DeployTask is exported from tasks module."""
        from deploy_satellite.tasks import DeployTask

        assert DeployTask is not None

    def test_undeploy_task_exported(self) -> None:
        """Test that UndeployTask is exported from tasks module."""
        from deploy_satellite.tasks import UndeployTask

        assert UndeployTask is not None
