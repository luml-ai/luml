"""Tests for model server components."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest


class TestModelServerClient:
    """Tests for ModelServerClient."""

    def test_init_default_timeout(self) -> None:
        """Test default initialization."""
        from deploy_satellite.model_server.client import ModelServerClient

        client = ModelServerClient()

        assert client._timeout == 45.0
        assert client._session is None

    def test_init_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        from deploy_satellite.model_server.client import ModelServerClient

        client = ModelServerClient(timeout=60.0)

        assert client._timeout == 60.0

    @pytest.mark.asyncio
    async def test_aenter_creates_session(self) -> None:
        """Test that __aenter__ creates an HTTP session."""
        from deploy_satellite.model_server.client import ModelServerClient

        client = ModelServerClient()
        assert client._session is None

        async with client:
            assert client._session is not None

    @pytest.mark.asyncio
    async def test_aexit_closes_session(self) -> None:
        """Test that __aexit__ closes the HTTP session."""
        from deploy_satellite.model_server.client import ModelServerClient

        client = ModelServerClient()

        async with client:
            pass  # session is used within context

        assert client._session is None

    def test_url_builds_correctly(self) -> None:
        """Test URL building for model server."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            url = ModelServerClient._url("dep-123")

            assert url == "http://sat-dep-123:8080"

    @pytest.mark.asyncio
    async def test_compute_success(self) -> None:
        """Test successful compute request."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"output": "result"}
            mock_response.raise_for_status = MagicMock()
            mock_session.post = AsyncMock(return_value=mock_response)

            client._session = mock_session

            result = await client.compute("dep-123", {"input": "data"})

            assert result == {"output": "result"}
            mock_session.post.assert_called_once_with(
                "http://sat-dep-123:8080/compute",
                json={"input": "data"},
            )

    @pytest.mark.asyncio
    async def test_is_healthy_success(self) -> None:
        """Test successful health check."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.get = AsyncMock(return_value=mock_response)

            client._session = mock_session

            result = await client.is_healthy("dep-123", timeout=1)

            assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_timeout(self) -> None:
        """Test health check timeout."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_session.get = AsyncMock(side_effect=Exception("Connection refused"))

            client._session = mock_session

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.is_healthy("dep-123", timeout=2)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_openapi_schema_success(self) -> None:
        """Test getting OpenAPI schema."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"openapi": "3.0.0"}
            mock_session.get = AsyncMock(return_value=mock_response)

            client._session = mock_session

            result = await client.get_openapi_schema("dep-123")

            assert result == {"openapi": "3.0.0"}

    @pytest.mark.asyncio
    async def test_get_openapi_schema_failure(self) -> None:
        """Test getting OpenAPI schema when not available."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_session.get = AsyncMock(side_effect=Exception("Not found"))

            client._session = mock_session

            result = await client.get_openapi_schema("dep-123")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_manifest_success(self) -> None:
        """Test getting manifest."""
        from deploy_satellite.model_server.client import ModelServerClient

        with patch("deploy_satellite.model_server.client.settings") as mock_settings:
            mock_settings.model_server_port = 8080

            client = ModelServerClient()
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"name": "test-model"}
            mock_session.get = AsyncMock(return_value=mock_response)

            client._session = mock_session

            result = await client.get_manifest("dep-123")

            assert result == {"name": "test-model"}


class TestModelServerHandler:
    """Tests for ModelServerHandler."""

    def test_init(self) -> None:
        """Test ModelServerHandler initialization."""
        from deploy_satellite.model_server.handler import ModelServerHandler

        handler = ModelServerHandler()

        assert handler.deployments == {}
        assert handler._openapi_cache_invalidation_callbacks == []

    @pytest.mark.asyncio
    async def test_add_single_deployment(self) -> None:
        """Test adding a single deployment."""
        from deploy_satellite.model_server.handler import ModelServerHandler

        handler = ModelServerHandler()

        # Mock the ModelServerClient
        with patch(
            "deploy_satellite.model_server.handler.ModelServerClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_manifest = AsyncMock(return_value={"name": "test"})
            mock_client.get_openapi_schema = AsyncMock(return_value={"openapi": "3.0"})
            mock_client_cls.return_value = mock_client

            await handler.add_single_deployment("dep-123", {"secret_key": "secret-id"})

            assert "dep-123" in handler.deployments
            deployment = handler.deployments["dep-123"]
            assert deployment.deployment_id == "dep-123"
            assert deployment.manifest == {"name": "test"}
            assert deployment.openapi_schema == {"openapi": "3.0"}

    @pytest.mark.asyncio
    async def test_remove_deployment(self) -> None:
        """Test removing a deployment."""
        from deploy_satellite.model_server.handler import ModelServerHandler
        from deploy_satellite.model_server.schemas import LocalDeployment

        handler = ModelServerHandler()
        handler.deployments["12345678-1234-5678-1234-567812345678"] = LocalDeployment(
            deployment_id="12345678-1234-5678-1234-567812345678",
        )

        await handler.remove_deployment(UUID("12345678-1234-5678-1234-567812345678"))

        assert "12345678-1234-5678-1234-567812345678" not in handler.deployments

    @pytest.mark.asyncio
    async def test_get_deployment(self) -> None:
        """Test getting a deployment."""
        from deploy_satellite.model_server.handler import ModelServerHandler
        from deploy_satellite.model_server.schemas import LocalDeployment

        handler = ModelServerHandler()
        local_dep = LocalDeployment(deployment_id="dep-123")
        handler.deployments["dep-123"] = local_dep

        result = await handler.get_deployment("dep-123")

        assert result is local_dep

    @pytest.mark.asyncio
    async def test_get_deployment_not_found(self) -> None:
        """Test getting a deployment that doesn't exist."""
        from deploy_satellite.model_server.handler import ModelServerHandler

        handler = ModelServerHandler()

        result = await handler.get_deployment("nonexistent")

        assert result is None

    def test_openapi_cache_invalidation_callback(self) -> None:
        """Test that OpenAPI cache invalidation callbacks are called."""
        from deploy_satellite.model_server.handler import ModelServerHandler

        handler = ModelServerHandler()
        callback = MagicMock()
        handler._openapi_cache_invalidation_callbacks.append(callback)

        handler._invalidate_openapi_cache()

        callback.assert_called_once()
