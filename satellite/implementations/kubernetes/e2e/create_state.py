import argparse
import base64
import io
import json
import tarfile
from pathlib import Path
from typing import Any

SATELLITE_ID = "00000000-0000-0000-0000-000000000001"
ORBIT_ID = "00000000-0000-0000-0000-000000000002"
ARTIFACT_ID = "30000000-0000-0000-0000-000000000001"
MAIN_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000001"
REPLICA_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000002"
GPU_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000003"
SATELLITE_TOKEN = "ci-satellite-token"
VALID_API_KEY = "ci-valid-api-key"
LAUNCH_TOKEN = "ci-monitoring-launch-token"
_TIMESTAMP = "2026-01-01T00:00:00+00:00"


def build_state(fixture_path: Path) -> dict[str, Any]:
    deployments = [
        _deployment(
            MAIN_DEPLOYMENT_ID,
            "monitored-stub",
            monitoring_mode="full",
            parameters={"health_check_timeout": 300},
        ),
        _deployment(
            REPLICA_DEPLOYMENT_ID,
            "replicated-stub",
            parameters={"replicas": 3, "health_check_timeout": 300},
        ),
        _deployment(
            GPU_DEPLOYMENT_ID,
            "gpu-stub",
            parameters={
                "use_gpu": True,
                "gpu_count": 1,
                "gpu_resource_name": "nvidia.com/gpu",
                "health_check_timeout": 300,
            },
        ),
    ]
    return {
        "token": SATELLITE_TOKEN,
        "deployments": deployments,
        "tasks": [
            task_record("20000000-0000-0000-0000-000000000001", MAIN_DEPLOYMENT_ID),
            task_record("20000000-0000-0000-0000-000000000002", REPLICA_DEPLOYMENT_ID),
            task_record("20000000-0000-0000-0000-000000000003", GPU_DEPLOYMENT_ID),
        ],
        "artifacts": [
            {
                "id": ARTIFACT_ID,
                "metadata": {"name": "stub-model.tar.gz"},
                "content_base64": base64.b64encode(_fixture_archive(fixture_path)).decode(),
            }
        ],
        "allowed_api_keys": [VALID_API_KEY],
        "monitoring_tokens": {
            LAUNCH_TOKEN: {
                "active": True,
                "claims": {
                    "deployment_id": MAIN_DEPLOYMENT_ID,
                    "satellite_id": SATELLITE_ID,
                    "user_id": "60000000-0000-0000-0000-000000000001",
                    "scope": "monitoring:read",
                    "jti": "70000000-0000-0000-0000-000000000001",
                    "exp": 4_102_444_800,
                },
            }
        },
    }


def _deployment(
    deployment_id: str,
    name: str,
    *,
    monitoring_mode: str = "off",
    parameters: dict[str, bool | int | str] | None = None,
) -> dict[str, Any]:
    return {
        "id": deployment_id,
        "orbit_id": ORBIT_ID,
        "satellite_id": SATELLITE_ID,
        "satellite_name": "kind satellite",
        "orbit_name": "kind",
        "name": name,
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "stub-model.tar.gz",
        "collection_id": "50000000-0000-0000-0000-000000000001",
        "inference_url": None,
        "monitoring_url": None,
        "status": "pending",
        "monitoring_mode": monitoring_mode,
        "satellite_parameters": parameters or {},
        "description": None,
        "dynamic_attributes_secrets": {},
        "env_variables_secrets": {},
        "env_variables": {},
        "schemas": None,
        "error_message": None,
        "provider_ref": None,
        "progress_note": None,
        "created_at": _TIMESTAMP,
        "updated_at": None,
    }


def task_record(task_id: str, deployment_id: str, task_type: str = "deploy") -> dict[str, Any]:
    return {
        "id": task_id,
        "satellite_id": SATELLITE_ID,
        "orbit_id": ORBIT_ID,
        "type": task_type,
        "payload": {"deployment_id": deployment_id},
        "status": "pending",
        "scheduled_at": _TIMESTAMP,
        "started_at": None,
        "finished_at": None,
        "result": None,
        "created_at": _TIMESTAMP,
        "updated_at": None,
    }


def _fixture_archive(fixture_path: Path) -> bytes:
    content = fixture_path.read_bytes()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        entry = tarfile.TarInfo("stub.json")
        entry.size = len(content)
        entry.mode = 0o644
        entry.mtime = 0
        archive.addfile(entry, io.BytesIO(content))
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the Kubernetes e2e fake-platform state")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    arguments.output.write_text(
        json.dumps(build_state(arguments.fixture), separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
