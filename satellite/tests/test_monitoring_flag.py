import httpx
import respx

from agent.handlers.model_server_handler import ModelServerHandler
from agent.schemas.deployments import Deployment, LocalDeployment


def _make_deployment(
    monitoring_mode: str = "off",
    deployment_id: str = "dep-1",
) -> Deployment:
    return Deployment(
        id=deployment_id,
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="test-sat",
        name="test-dep",
        artifact_id="art-1",
        artifact_name="model-a",
        collection_id="col-1",
        status="active",
        monitoring_mode=monitoring_mode,
        created_at="2026-01-01T00:00:00Z",
    )


class TestReadMonitoringEnabled:
    def test_true_when_full(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("full") is True

    def test_false_when_off(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("off") is False

    def test_false_when_none(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled(None) is False

    def test_true_case_insensitive(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("FULL") is True

    def test_false_when_unknown(self) -> None:
        assert ModelServerHandler._read_monitoring_enabled("garbage") is False


class TestLocalDeploymentMonitoringDefault:
    def test_defaults_to_false(self) -> None:
        ld = LocalDeployment(deployment_id="dep-1")
        assert ld.monitoring_enabled is False

    def test_can_be_set_true(self) -> None:
        ld = LocalDeployment(deployment_id="dep-1", monitoring_enabled=True)
        assert ld.monitoring_enabled is True


class TestAddDeploymentCarriesFlag:
    @respx.mock
    async def test_monitoring_enabled_propagated(self, mock_model_server: None) -> None:
        handler = ModelServerHandler()
        dep = _make_deployment(monitoring_mode="full")
        await handler.add_deployment(dep)

        local = handler.deployments[dep.id]
        assert local.monitoring_enabled is True

    @respx.mock
    async def test_monitoring_disabled_by_default(self, mock_model_server: None) -> None:
        handler = ModelServerHandler()
        dep = _make_deployment()
        await handler.add_deployment(dep)

        local = handler.deployments[dep.id]
        assert local.monitoring_enabled is False


class TestSyncDeploymentsCarriesFlag:
    @respx.mock
    async def test_sync_reads_monitoring_mode(self) -> None:
        handler = ModelServerHandler()

        platform_url = "https://api.luml.ai"
        respx.get(f"{platform_url}/satellites/v1/deployments").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "dep-sync-1",
                        "status": "active",
                        "monitoring_mode": "full",
                        "dynamic_attributes_secrets": {},
                    }
                ],
            )
        )

        # Mock model server endpoints for this specific deployment
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/healthz").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/manifest").mock(
            return_value=httpx.Response(200, json={"name": "test", "version": "1"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-1:\d+/openapi\.json").mock(
            return_value=httpx.Response(200, json={"openapi": "3.0.0"})
        )

        # We need to mock docker. sync_deployments creates its own clients,
        # so we patch the docker check at the handler level.
        from unittest.mock import AsyncMock, patch

        mock_docker = AsyncMock()
        mock_docker.check_container_running = AsyncMock()
        mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
        mock_docker.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.handlers.model_server_handler.DockerService", return_value=mock_docker):
            await handler.sync_deployments()

        assert "dep-sync-1" in handler.deployments
        assert handler.deployments["dep-sync-1"].monitoring_enabled is True

    @respx.mock
    async def test_sync_absent_mode_means_off(self) -> None:
        handler = ModelServerHandler()

        platform_url = "https://api.luml.ai"
        respx.get(f"{platform_url}/satellites/v1/deployments").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "dep-sync-2",
                        "status": "active",
                        "dynamic_attributes_secrets": {},
                    }
                ],
            )
        )

        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/healthz").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/manifest").mock(
            return_value=httpx.Response(200, json={"name": "test", "version": "1"})
        )
        respx.get(url__regex=r"http://sat-dep-sync-2:\d+/openapi\.json").mock(
            return_value=httpx.Response(200, json={"openapi": "3.0.0"})
        )

        from unittest.mock import AsyncMock, patch

        mock_docker = AsyncMock()
        mock_docker.check_container_running = AsyncMock()
        mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
        mock_docker.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.handlers.model_server_handler.DockerService", return_value=mock_docker):
            await handler.sync_deployments()

        assert "dep-sync-2" in handler.deployments
        assert handler.deployments["dep-sync-2"].monitoring_enabled is False
