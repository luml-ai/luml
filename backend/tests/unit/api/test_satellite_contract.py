from typing import Any, cast

from fastapi.testclient import TestClient
from luml.service import AppService


def test_satellite_contract_is_public_versioned_and_worker_only() -> None:
    response = TestClient(AppService()).get("/satellites/v1/contract")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["api_version"] == 1

    paths = cast(dict[str, dict[str, Any]], payload["openapi"]["paths"])
    assert paths
    assert all(path.startswith("/satellites/v1/") for path in paths)
    assert "post" in paths["/satellites/v1/pair"]
    assert "get" in paths["/satellites/v1/tasks"]
    assert "get" in paths["/satellites/v1/contract"]
    assert not any("organizations" in path for path in paths)
