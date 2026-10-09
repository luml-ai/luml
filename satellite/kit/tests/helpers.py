from datetime import UTC, datetime
from typing import Any

DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000001"
TASK_ID = "20000000-0000-0000-0000-000000000001"
ARTIFACT_ID = "30000000-0000-0000-0000-000000000001"
SECRET_ID = "40000000-0000-0000-0000-000000000001"


def deployment_record(**overrides: object) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": DEPLOYMENT_ID,
        "orbit_id": "00000000-0000-0000-0000-000000000002",
        "satellite_id": "00000000-0000-0000-0000-000000000001",
        "satellite_name": "Fixture satellite",
        "orbit_name": "Production",
        "name": "classifier",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "model.tar.gz",
        "collection_id": "50000000-0000-0000-0000-000000000001",
        "inference_url": None,
        "monitoring_url": None,
        "status": "pending",
        "monitoring_mode": "off",
        "satellite_parameters": {},
        "description": None,
        "dynamic_attributes_secrets": {},
        "env_variables_secrets": {},
        "env_variables": {},
        "schemas": None,
        "error_message": None,
        "provider_ref": None,
        "progress_note": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "updated_at": None,
    }
    record.update(overrides)
    return record


def task_record(**overrides: object) -> dict[str, Any]:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    record: dict[str, Any] = {
        "id": TASK_ID,
        "satellite_id": "00000000-0000-0000-0000-000000000001",
        "orbit_id": "00000000-0000-0000-0000-000000000002",
        "type": "deploy",
        "payload": {"deployment_id": DEPLOYMENT_ID},
        "status": "pending",
        "scheduled_at": timestamp,
        "started_at": None,
        "finished_at": None,
        "result": None,
        "created_at": timestamp,
        "updated_at": None,
    }
    record.update(overrides)
    return record
