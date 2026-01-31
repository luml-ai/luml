"""Pytest configuration and fixtures for SDK tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from luml_satellite_sdk import PlatformClient
from luml_satellite_sdk.schemas import (
    Deployment,
    SatelliteQueueTask,
)


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Create a mock httpx AsyncClient."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def platform_client() -> PlatformClient:
    """Create a PlatformClient instance for testing."""
    return PlatformClient(
        base_url="https://api.example.com",
        token="test-token",
        timeout_s=10.0,
    )


@pytest.fixture
def sample_task_dict() -> dict[str, Any]:
    """Create a sample task dictionary."""
    return {
        "id": "task-123",
        "satellite_id": "sat-456",
        "orbit_id": "orbit-789",
        "type": "deploy",
        "payload": {"deployment_id": "dep-001"},
        "status": "pending",
        "scheduled_at": "2024-01-15T10:00:00Z",
        "created_at": "2024-01-15T09:00:00Z",
    }


@pytest.fixture
def sample_queue_task(sample_task_dict: dict[str, Any]) -> SatelliteQueueTask:
    """Create a sample SatelliteQueueTask."""
    return SatelliteQueueTask.model_validate(sample_task_dict)


@pytest.fixture
def sample_deployment_dict() -> dict[str, Any]:
    """Create a sample deployment dictionary."""
    return {
        "id": "dep-001",
        "orbit_id": "orbit-789",
        "satellite_id": "sat-456",
        "satellite_name": "test-satellite",
        "name": "test-deployment",
        "model_id": "model-123",
        "model_artifact_name": "test-model",
        "collection_id": "col-001",
        "inference_url": "http://localhost:8000/inference",
        "status": "active",
        "created_at": "2024-01-15T09:00:00Z",
    }


@pytest.fixture
def sample_deployment(sample_deployment_dict: dict[str, Any]) -> Deployment:
    """Create a sample Deployment."""
    return Deployment.model_validate(sample_deployment_dict)
