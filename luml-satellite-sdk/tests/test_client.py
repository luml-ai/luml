"""Tests for PlatformClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import httpx
import pytest

from luml_satellite_sdk import PlatformClient
from luml_satellite_sdk.schemas import (
    Deployment,
    SatelliteTaskStatus,
)


class TestPlatformClientInit:
    """Tests for PlatformClient initialization."""

    def test_init_sets_base_url(self) -> None:
        """Test that base_url is set correctly."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )
        assert client.base_url == "https://api.example.com"

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slash is stripped from base_url."""
        client = PlatformClient(
            base_url="https://api.example.com/",
            token="test-token",
        )
        assert client.base_url == "https://api.example.com"

    def test_init_sets_default_timeout(self) -> None:
        """Test that default timeout is set."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )
        assert client._timeout == 30.0

    def test_init_sets_custom_timeout(self) -> None:
        """Test that custom timeout can be set."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
            timeout_s=60.0,
        )
        assert client._timeout == 60.0

    def test_init_sets_auth_header(self) -> None:
        """Test that authorization header is set correctly."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="my-secret-token",
        )
        assert client._headers["Authorization"] == "Bearer my-secret-token"
        assert client._headers["Content-Type"] == "application/json"


class TestPlatformClientContextManager:
    """Tests for PlatformClient context manager."""

    @pytest.mark.asyncio
    async def test_aenter_creates_session(self) -> None:
        """Test that __aenter__ creates an HTTP session."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )
        assert client._session is None

        async with client:
            assert client._session is not None
            assert isinstance(client._session, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_aexit_closes_session(self) -> None:
        """Test that __aexit__ closes the HTTP session."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )

        async with client:
            pass  # session is used within context

        assert client._session is None


class TestPlatformClientUrl:
    """Tests for URL building."""

    def test_url_with_leading_slash(self) -> None:
        """Test URL building with leading slash."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )
        assert client._url("/test/path") == "https://api.example.com/test/path"

    def test_url_without_leading_slash(self) -> None:
        """Test URL building without leading slash."""
        client = PlatformClient(
            base_url="https://api.example.com",
            token="test-token",
        )
        assert client._url("test/path") == "https://api.example.com/test/path"


class TestPlatformClientListTasks:
    """Tests for list_tasks method."""

    @pytest.mark.asyncio
    async def test_list_tasks_without_status(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test listing tasks without status filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "task-1"}, {"id": "task-2"}]
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        tasks = await platform_client.list_tasks()

        assert len(tasks) == 2
        mock_httpx_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_enum(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test listing tasks with SatelliteTaskStatus enum."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "task-1", "status": "pending"}]
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        tasks = await platform_client.list_tasks(status=SatelliteTaskStatus.PENDING)

        assert len(tasks) == 1
        mock_httpx_client.get.assert_called_once()
        call_kwargs = mock_httpx_client.get.call_args
        assert call_kwargs[1]["params"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_string(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test listing tasks with status as string."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        tasks = await platform_client.list_tasks(status="running")

        assert tasks == []
        call_kwargs = mock_httpx_client.get.call_args
        assert call_kwargs[1]["params"]["status"] == "running"


class TestPlatformClientUpdateTaskStatus:
    """Tests for update_task_status method."""

    @pytest.mark.asyncio
    async def test_update_task_status_with_enum(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test updating task status with enum."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "task-1", "status": "running"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        platform_client._session = mock_httpx_client

        result = await platform_client.update_task_status(
            "task-1", SatelliteTaskStatus.RUNNING
        )

        assert result["status"] == "running"
        mock_httpx_client.post.assert_called_once()
        call_kwargs = mock_httpx_client.post.call_args
        assert call_kwargs[1]["json"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_update_task_status_with_result(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test updating task status with result data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "task-1", "status": "done"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        platform_client._session = mock_httpx_client

        await platform_client.update_task_status(
            "task-1", "done", result={"output": "success"}
        )

        call_kwargs = mock_httpx_client.post.call_args
        assert call_kwargs[1]["json"]["result"] == {"output": "success"}


class TestPlatformClientPairSatellite:
    """Tests for pair_satellite method."""

    @pytest.mark.asyncio
    async def test_pair_satellite(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test pairing satellite with platform."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"satellite_id": "sat-123", "paired": True}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        platform_client._session = mock_httpx_client

        result = await platform_client.pair_satellite(
            base_url="http://localhost:8000",
            capabilities={"deploy": {"version": 1}},
            slug="my-satellite",
        )

        assert result["paired"] is True
        call_kwargs = mock_httpx_client.post.call_args
        assert call_kwargs[1]["json"]["base_url"] == "http://localhost:8000"
        assert call_kwargs[1]["json"]["capabilities"] == {"deploy": {"version": 1}}
        assert call_kwargs[1]["json"]["slug"] == "my-satellite"


class TestPlatformClientDeployment:
    """Tests for deployment-related methods."""

    @pytest.mark.asyncio
    async def test_get_deployment(
        self,
        platform_client: PlatformClient,
        mock_httpx_client: MagicMock,
        sample_deployment_dict: dict[str, Any],
    ) -> None:
        """Test getting deployment details."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_deployment_dict
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        deployment = await platform_client.get_deployment("dep-001")

        assert isinstance(deployment, Deployment)
        assert deployment.id == "dep-001"
        assert deployment.name == "test-deployment"

    @pytest.mark.asyncio
    async def test_update_deployment_status(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test updating deployment status."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "dep-001", "status": "active"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.patch.return_value = mock_response

        platform_client._session = mock_httpx_client

        result = await platform_client.update_deployment_status("dep-001", "active")

        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_delete_deployment(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test deleting a deployment."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.delete.return_value = mock_response

        platform_client._session = mock_httpx_client

        await platform_client.delete_deployment(
            UUID("12345678-1234-5678-1234-567812345678")
        )

        mock_httpx_client.delete.assert_called_once()


class TestPlatformClientSecrets:
    """Tests for secrets-related methods."""

    @pytest.mark.asyncio
    async def test_get_orbit_secrets(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test getting orbit secrets."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "secret-1", "name": "api-key"},
            {"id": "secret-2", "name": "db-password"},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        secrets = await platform_client.get_orbit_secrets()

        assert len(secrets) == 2
        assert secrets[0]["name"] == "api-key"

    @pytest.mark.asyncio
    async def test_get_orbit_secret(
        self, platform_client: PlatformClient, mock_httpx_client: MagicMock
    ) -> None:
        """Test getting a specific orbit secret."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "secret-1", "value": "secret-value"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get.return_value = mock_response

        platform_client._session = mock_httpx_client

        secret = await platform_client.get_orbit_secret(
            UUID("12345678-1234-5678-1234-567812345678")
        )

        assert secret["value"] == "secret-value"
