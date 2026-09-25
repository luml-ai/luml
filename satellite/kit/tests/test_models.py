from datetime import UTC, datetime

from luml_satellite.wire import Deployment, SatelliteQueueTask
from tests.helpers import deployment_record, task_record


def test_platform_models_preserve_unknown_fields() -> None:
    deployment = Deployment.model_validate(deployment_record(future_field={"nested": "value"}))

    assert deployment.model_dump()["future_field"] == {"nested": "value"}


def test_deployment_accepts_legacy_null_mappings() -> None:
    deployment = Deployment.model_validate(
        deployment_record(
            satellite_parameters=None,
            dynamic_attributes_secrets=None,
            env_variables_secrets=None,
            env_variables=None,
        )
    )

    assert deployment.satellite_parameters is None
    assert deployment.dynamic_attributes_secrets is None
    assert deployment.env_variables_secrets is None
    assert deployment.env_variables is None


def test_task_type_is_a_plain_string_and_preserves_unknown_fields() -> None:
    task = SatelliteQueueTask.model_validate(
        task_record(type="custom.vendor.sync", future_field=True)
    )

    assert task.type == "custom.vendor.sync"
    assert task.model_dump()["future_field"] is True
    assert task.created_at == datetime(2026, 1, 1, tzinfo=UTC)
