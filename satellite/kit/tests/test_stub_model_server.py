import json
import threading
from pathlib import Path

import httpx
import pytest

from luml_satellite.testing import create_stub_model_server

KIT_ROOT = Path(__file__).parents[1]


def test_stub_model_server_serves_the_model_contract_and_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_id = "fixture-artifact"
    artifact = tmp_path / artifact_id
    artifact.mkdir()
    (artifact / "stub.json").write_text('{"prediction": 42}', encoding="utf-8")
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_ARTIFACT_ID", artifact_id)
    monkeypatch.setenv("HOSTNAME", "stub-replica")
    server = create_stub_model_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        address = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=address) as client:
            health = client.get("/healthz")
            manifest = client.get("/manifest")
            schema = client.get("/openapi.json")
            profile = client.get("/reference_profile")
            compute = client.post("/compute", json={"value": 7})
            invalid = client.post(
                "/compute",
                content=b"not-json",
                headers={"Content-Type": "application/json"},
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert health.json() == {"status": "healthy"}
    assert manifest.json()["producer_tags"] == ["luml.ai::tabular_monitoring:v1"]
    assert schema.json()["paths"]["/compute"]["post"]["summary"] == "Compute"
    assert profile.json()["profile_status"] == "ready"
    assert compute.json() == {
        "artifact_id": artifact_id,
        "fixture": {"prediction": 42},
        "inputs": {"value": 7},
        "replica": "stub-replica",
    }
    assert compute.headers["X-Stub-Replica"] == "stub-replica"
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": "Invalid JSON"}


def test_stub_model_server_is_unhealthy_without_a_fetched_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_ARTIFACT_ID", "missing")
    server = create_stub_model_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = httpx.get(f"http://127.0.0.1:{server.server_port}/healthz")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.status_code == 503
    assert response.json() == {"detail": "Fixture artifact unavailable"}


def test_stub_model_image_is_non_root_and_includes_the_fixture() -> None:
    dockerfile = (KIT_ROOT / "Dockerfile.stub-model").read_text(encoding="utf-8")
    fixture = KIT_ROOT / "e2e/fixtures/stub-model/stub.json"

    assert dockerfile.startswith("FROM python:3.14-")
    assert "chgrp -R 0 /app" in dockerfile
    assert "chmod -R g=u /app" in dockerfile
    assert "USER 10001:0" in dockerfile
    assert 'CMD ["luml-stub-model-server"]' in dockerfile
    assert json.loads(fixture.read_text(encoding="utf-8")) == {"prediction": 42}
