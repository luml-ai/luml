"""Pytest configuration and fixtures for deploy satellite tests."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set required environment variables before importing deploy_satellite modules
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("SATELLITE_ID", "test-satellite-id")

from luml_satellite_sdk.schemas import (
    Deployment,
    SatelliteQueueTask,
)


@pytest.fixture
def mock_docker_client() -> MagicMock:
    """Create a mock aiodocker client."""
    client = MagicMock()
    client.containers = MagicMock()
    client.containers.list = AsyncMock(return_value=[])
    client.containers.get = AsyncMock()
    client.containers.create = AsyncMock()
    client.containers.create_or_replace = AsyncMock()
    client.images = MagicMock()
    client.images.get = AsyncMock()
    client.images.pull = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_platform_client() -> MagicMock:
    """Create a mock platform client."""
    client = MagicMock()
    client.list_tasks = AsyncMock(return_value=[])
    client.update_task_status = AsyncMock()
    client.update_deployment_status = AsyncMock()
    client.update_deployment = AsyncMock()
    client.delete_deployment = AsyncMock()
    client.get_deployment = AsyncMock()
    client.get_model_artifact = AsyncMock()
    client.get_orbit_secrets = AsyncMock(return_value=[])
    return client


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
        "satellite_parameters": {"max_memory": 1024},
        "env_variables": {"ENV_VAR": "value"},
        "env_variables_secrets": {},
        "dynamic_attributes_secrets": {},
        "created_at": "2024-01-15T09:00:00Z",
    }


@pytest.fixture
def sample_deployment(sample_deployment_dict: dict[str, Any]) -> Deployment:
    """Create a sample Deployment."""
    return Deployment.model_validate(sample_deployment_dict)


@pytest.fixture
def sample_deploy_task_dict() -> dict[str, Any]:
    """Create a sample deploy task dictionary."""
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
def sample_undeploy_task_dict() -> dict[str, Any]:
    """Create a sample undeploy task dictionary."""
    return {
        "id": "task-456",
        "satellite_id": "sat-456",
        "orbit_id": "orbit-789",
        "type": "undeploy",
        "payload": {"deployment_id": "dep-001"},
        "status": "pending",
        "scheduled_at": "2024-01-15T10:00:00Z",
        "created_at": "2024-01-15T09:00:00Z",
    }


@pytest.fixture
def sample_queue_task(sample_deploy_task_dict: dict[str, Any]) -> SatelliteQueueTask:
    """Create a sample SatelliteQueueTask."""
    return SatelliteQueueTask.model_validate(sample_deploy_task_dict)
