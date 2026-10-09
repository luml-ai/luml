import json
from pathlib import Path
from typing import Any

from luml_api.resources.monitoring import MONITORING_API_IMPLEMENTATIONS

OPENAPI_SNAPSHOT = (
    Path(__file__).resolve().parents[5]
    / "satellite"
    / "implementations"
    / "docker"
    / "tests"
    / "snapshots"
    / "static_openapi.json"
)
MONITORING_PATH_PREFIX = "/deployments/{deployment_id}/monitoring"


def test_native_monitoring_operations_match_satellite_openapi() -> None:
    schema: dict[str, Any] = json.loads(OPENAPI_SNAPSHOT.read_text())
    paths = schema["paths"]

    for implementation in MONITORING_API_IMPLEMENTATIONS.values():
        for operation_name, operation in implementation.operations.items():
            path = f"{MONITORING_PATH_PREFIX}/{operation.path}"
            assert path in paths, (
                f"monitoring v{implementation.version} operation {operation_name!r} "
                f"uses missing path {path!r}"
            )
            assert "get" in paths[path], (
                f"monitoring v{implementation.version} operation {operation_name!r} "
                f"has no GET contract at {path!r}"
            )
            openapi_query_parameters = {
                parameter["name"]
                for parameter in paths[path]["get"].get("parameters", [])
                if parameter.get("in") == "query"
            }
            missing_parameters = operation.query_parameters - openapi_query_parameters
            assert not missing_parameters, (
                f"monitoring v{implementation.version} operation {operation_name!r} "
                f"uses query parameters absent from the Satellite contract: "
                f"{sorted(missing_parameters)}"
            )
