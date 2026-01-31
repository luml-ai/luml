"""Tests for DockerService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from aiodocker.exceptions import DockerError
from luml_satellite_sdk import ContainerNotFoundError, ContainerNotRunningError


class TestDockerServiceInit:
    """Tests for DockerService initialization."""

    def test_init_default_values(self) -> None:
        """Test default initialization values."""
        with patch("deploy_satellite.docker.aiodocker.Docker"):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            assert service.network_name == "satellite_satellite-network"
            assert service.model_server_port == 8080

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        with patch("deploy_satellite.docker.aiodocker.Docker"):
            from deploy_satellite.docker import DockerService

            service = DockerService(
                network_name="custom-network",
                model_server_port=9000,
            )

            assert service.network_name == "custom-network"
            assert service.model_server_port == 9000


class TestDockerServiceContextManager:
    """Tests for DockerService context manager."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self) -> None:
        """Test that __aenter__ returns self."""
        with patch("deploy_satellite.docker.aiodocker.Docker"):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            result = await service.__aenter__()

            assert result is service

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self) -> None:
        """Test that __aexit__ closes the Docker client."""
        mock_docker = MagicMock()
        mock_docker.close = AsyncMock()

        mock_target = "deploy_satellite.docker.aiodocker.Docker"
        with patch(mock_target, return_value=mock_docker):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            await service.__aexit__(None, None, None)

            mock_docker.close.assert_called_once()


class TestDockerServiceRunModelContainer:
    """Tests for DockerService run_model_container method."""

    @pytest.mark.asyncio
    async def test_run_model_container_creates_container(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test that run_model_container creates and starts a container."""
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_docker_client.containers.create_or_replace = AsyncMock(
            return_value=mock_container
        )

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            container = await service.run_model_container(
                image="test-image:latest",
                name="test-container",
            )

            assert container is mock_container
            mock_container.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_model_container_with_env(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test that run_model_container passes environment variables."""
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_docker_client.containers.create_or_replace = AsyncMock(
            return_value=mock_container
        )

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            await service.run_model_container(
                image="test-image:latest",
                name="test-container",
                env={"MY_VAR": "my_value"},
            )

            call_kwargs = mock_docker_client.containers.create_or_replace.call_args
            config = call_kwargs.kwargs["config"]
            # Check that env is in the config
            env_list = config.get("Env", [])
            assert any("MY_VAR=my_value" in str(e) for e in env_list)

    @pytest.mark.asyncio
    async def test_run_model_container_with_labels(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test that run_model_container passes labels."""
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_docker_client.containers.create_or_replace = AsyncMock(
            return_value=mock_container
        )

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            await service.run_model_container(
                image="test-image:latest",
                name="test-container",
                labels={"df.deployment_id": "dep-123"},
            )

            call_kwargs = mock_docker_client.containers.create_or_replace.call_args
            config = call_kwargs.kwargs["config"]
            assert config["Labels"] == {"df.deployment_id": "dep-123"}


class TestDockerServiceRemoveModelContainer:
    """Tests for DockerService remove_model_container method."""

    @pytest.mark.asyncio
    async def test_remove_model_container_success(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test successfully removing a container."""
        mock_container = MagicMock()
        mock_container.show = AsyncMock(
            return_value={
                "Config": {"Labels": {"df.model_id": "model-123"}},
            }
        )
        mock_container.stop = AsyncMock()
        mock_container.delete = AsyncMock()
        mock_docker_client.containers.get = AsyncMock(return_value=mock_container)

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()
            deployment_id = UUID("12345678-1234-5678-1234-567812345678")

            success, model_id = await service.remove_model_container(
                deployment_id=deployment_id
            )

            assert success is True
            assert model_id == "model-123"
            mock_container.stop.assert_called_once()
            mock_container.delete.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_remove_model_container_not_found(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test removing a container that doesn't exist."""
        mock_docker_client.containers.get = AsyncMock(
            side_effect=DockerError(404, "not found")
        )

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()
            deployment_id = UUID("12345678-1234-5678-1234-567812345678")

            success, model_id = await service.remove_model_container(
                deployment_id=deployment_id
            )

            assert success is False
            assert model_id is None


class TestDockerServiceIsModelInUse:
    """Tests for DockerService is_model_in_use method."""

    @pytest.mark.asyncio
    async def test_model_in_use(self, mock_docker_client: MagicMock) -> None:
        """Test detecting when a model is in use."""
        mock_container = MagicMock()
        mock_container.show = AsyncMock(
            return_value={
                "Config": {"Labels": {"df.model_id": "model-123"}},
            }
        )
        mock_docker_client.containers.list = AsyncMock(return_value=[mock_container])

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            in_use = await service.is_model_in_use("model-123")

            assert in_use is True

    @pytest.mark.asyncio
    async def test_model_not_in_use(self, mock_docker_client: MagicMock) -> None:
        """Test detecting when a model is not in use."""
        mock_container = MagicMock()
        mock_container.show = AsyncMock(
            return_value={
                "Config": {"Labels": {"df.model_id": "different-model"}},
            }
        )
        mock_docker_client.containers.list = AsyncMock(return_value=[mock_container])

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            in_use = await service.is_model_in_use("model-123")

            assert in_use is False

    @pytest.mark.asyncio
    async def test_no_containers(self, mock_docker_client: MagicMock) -> None:
        """Test when there are no containers."""
        mock_docker_client.containers.list = AsyncMock(return_value=[])

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            in_use = await service.is_model_in_use("model-123")

            assert in_use is False


class TestDockerServiceCheckContainerRunning:
    """Tests for DockerService check_container_running method."""

    @pytest.mark.asyncio
    async def test_container_running(self, mock_docker_client: MagicMock) -> None:
        """Test when container is running."""
        mock_container = MagicMock()
        mock_container.show = AsyncMock(return_value={"State": {"Status": "running"}})
        mock_docker_client.containers.get = AsyncMock(return_value=mock_container)

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            # Should not raise
            await service.check_container_running("dep-123")

    @pytest.mark.asyncio
    async def test_container_not_found(self, mock_docker_client: MagicMock) -> None:
        """Test when container is not found."""
        mock_docker_client.containers.get = AsyncMock(
            side_effect=DockerError(404, "not found")
        )

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            with pytest.raises(ContainerNotFoundError) as exc_info:
                await service.check_container_running("dep-123")

            assert exc_info.value.container_id == "dep-123"

    @pytest.mark.asyncio
    async def test_container_not_running(self, mock_docker_client: MagicMock) -> None:
        """Test when container exists but is not running."""
        mock_container = MagicMock()
        mock_container.show = AsyncMock(return_value={"State": {"Status": "exited"}})
        mock_docker_client.containers.get = AsyncMock(return_value=mock_container)

        with patch(
            "deploy_satellite.docker.aiodocker.Docker",
            return_value=mock_docker_client,
        ):
            from deploy_satellite.docker import DockerService

            service = DockerService()

            with pytest.raises(ContainerNotRunningError) as exc_info:
                await service.check_container_running("dep-123")

            assert exc_info.value.container_id == "dep-123"
            assert exc_info.value.current_status == "exited"
