"""Tests for SDK schemas."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from luml_satellite_sdk.schemas import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)


class TestSatelliteTaskType:
    """Tests for SatelliteTaskType enum."""

    def test_deploy_value(self) -> None:
        """Test DEPLOY enum value."""
        assert SatelliteTaskType.DEPLOY == "deploy"
        assert SatelliteTaskType.DEPLOY.value == "deploy"

    def test_undeploy_value(self) -> None:
        """Test UNDEPLOY enum value."""
        assert SatelliteTaskType.UNDEPLOY == "undeploy"
        assert SatelliteTaskType.UNDEPLOY.value == "undeploy"


class TestSatelliteTaskStatus:
    """Tests for SatelliteTaskStatus enum."""

    def test_pending_value(self) -> None:
        """Test PENDING enum value."""
        assert SatelliteTaskStatus.PENDING == "pending"

    def test_running_value(self) -> None:
        """Test RUNNING enum value."""
        assert SatelliteTaskStatus.RUNNING == "running"

    def test_done_value(self) -> None:
        """Test DONE enum value."""
        assert SatelliteTaskStatus.DONE == "done"

    def test_failed_value(self) -> None:
        """Test FAILED enum value."""
        assert SatelliteTaskStatus.FAILED == "failed"


class TestSatelliteQueueTask:
    """Tests for SatelliteQueueTask schema."""

    def test_valid_task(self) -> None:
        """Test creating a valid task."""
        task = SatelliteQueueTask(
            id="task-123",
            satellite_id="sat-456",
            orbit_id="orbit-789",
            type=SatelliteTaskType.DEPLOY,
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=datetime(2024, 1, 15, 10, 0, 0),
            created_at=datetime(2024, 1, 15, 9, 0, 0),
        )

        assert task.id == "task-123"
        assert task.type == SatelliteTaskType.DEPLOY
        assert task.status == SatelliteTaskStatus.PENDING

    def test_task_with_payload(self) -> None:
        """Test task with payload."""
        task = SatelliteQueueTask(
            id="task-123",
            satellite_id="sat-456",
            orbit_id="orbit-789",
            type=SatelliteTaskType.DEPLOY,
            payload={"deployment_id": "dep-001"},
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=datetime(2024, 1, 15, 10, 0, 0),
            created_at=datetime(2024, 1, 15, 9, 0, 0),
        )

        assert task.payload == {"deployment_id": "dep-001"}

    def test_task_from_dict(self) -> None:
        """Test creating task from dictionary."""
        data = {
            "id": "task-123",
            "satellite_id": "sat-456",
            "orbit_id": "orbit-789",
            "type": "deploy",
            "status": "pending",
            "scheduled_at": "2024-01-15T10:00:00",
            "created_at": "2024-01-15T09:00:00",
        }

        task = SatelliteQueueTask.model_validate(data)

        assert task.id == "task-123"
        assert task.type == SatelliteTaskType.DEPLOY

    def test_task_missing_required_field(self) -> None:
        """Test that missing required fields raise error."""
        with pytest.raises(ValidationError):
            SatelliteQueueTask(
                id="task-123",
                # Missing satellite_id, orbit_id, etc.
            )

    def test_task_optional_fields_default_to_none(self) -> None:
        """Test that optional fields default to None."""
        task = SatelliteQueueTask(
            id="task-123",
            satellite_id="sat-456",
            orbit_id="orbit-789",
            type=SatelliteTaskType.DEPLOY,
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=datetime(2024, 1, 15, 10, 0, 0),
            created_at=datetime(2024, 1, 15, 9, 0, 0),
        )

        assert task.payload is None
        assert task.started_at is None
        assert task.finished_at is None
        assert task.result is None
        assert task.updated_at is None


class TestDeploymentStatus:
    """Tests for DeploymentStatus enum."""

    def test_pending_value(self) -> None:
        """Test PENDING enum value."""
        assert DeploymentStatus.PENDING == "pending"

    def test_active_value(self) -> None:
        """Test ACTIVE enum value."""
        assert DeploymentStatus.ACTIVE == "active"

    def test_failed_value(self) -> None:
        """Test FAILED enum value."""
        assert DeploymentStatus.FAILED == "failed"


class TestErrorMessage:
    """Tests for ErrorMessage schema."""

    def test_valid_error_message(self) -> None:
        """Test creating a valid error message."""
        error = ErrorMessage(
            reason="deployment_failed",
            error="Container failed to start",
        )

        assert error.reason == "deployment_failed"
        assert error.error == "Container failed to start"


class TestDeploymentUpdate:
    """Tests for DeploymentUpdate schema."""

    def test_update_status_only(self) -> None:
        """Test update with status only."""
        update = DeploymentUpdate(status=DeploymentStatus.ACTIVE)

        assert update.status == DeploymentStatus.ACTIVE
        assert update.inference_url is None
        assert update.schemas is None
        assert update.error_message is None

    def test_update_with_all_fields(self) -> None:
        """Test update with all fields."""
        update = DeploymentUpdate(
            status=DeploymentStatus.ACTIVE,
            inference_url="http://localhost:8000/inference",
            schemas={"input": {"type": "object"}},
            error_message=ErrorMessage(reason="test", error="test error"),
        )

        assert update.status == DeploymentStatus.ACTIVE
        assert update.inference_url == "http://localhost:8000/inference"
        assert update.schemas == {"input": {"type": "object"}}
        assert update.error_message is not None


class TestDeployment:
    """Tests for Deployment schema."""

    def test_valid_deployment(self) -> None:
        """Test creating a valid deployment."""
        deployment = Deployment(
            id="dep-001",
            orbit_id="orbit-789",
            satellite_id="sat-456",
            satellite_name="test-satellite",
            name="test-deployment",
            model_id="model-123",
            model_artifact_name="test-model",
            collection_id="col-001",
            status="active",
            created_at="2024-01-15T09:00:00Z",
        )

        assert deployment.id == "dep-001"
        assert deployment.name == "test-deployment"
        assert deployment.status == "active"

    def test_deployment_from_dict(self) -> None:
        """Test creating deployment from dictionary."""
        data = {
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

        deployment = Deployment.model_validate(data)

        assert deployment.id == "dep-001"
        assert deployment.inference_url == "http://localhost:8000/inference"

    def test_deployment_optional_fields(self) -> None:
        """Test deployment optional fields default correctly."""
        deployment = Deployment(
            id="dep-001",
            orbit_id="orbit-789",
            satellite_id="sat-456",
            satellite_name="test-satellite",
            name="test-deployment",
            model_id="model-123",
            model_artifact_name="test-model",
            collection_id="col-001",
            status="active",
            created_at="2024-01-15T09:00:00Z",
        )

        assert deployment.inference_url is None
        assert deployment.satellite_parameters == {}
        assert deployment.description is None
        assert deployment.env_variables == {}
        assert deployment.tags is None
