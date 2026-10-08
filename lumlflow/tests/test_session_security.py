from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from luml.experiments.tracker import ExperimentTracker
from lumlflow.api.experiments import experiments_handler
from lumlflow.service import AppService


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    tracker = ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")
    with patch.object(experiments_handler, "tracker", tracker):
        yield TestClient(AppService())


def test_api_requires_session_token(client: TestClient) -> None:
    assert client.get("/api/auth/status").status_code == 401
    assert (
        client.get(
            "/api/auth/status", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    assert client.post("/api/auth/api-key", json={"api_key": "test"}).status_code == 401
    assert (
        client.get(
            "/api/auth/status", params={"token": client.app.state.session_token}
        ).status_code
        == 401
    )


def test_session_tokens_are_unique_and_not_exposed(client: TestClient) -> None:
    other = AppService()
    assert client.app.state.session_token != other.state.session_token
    response = client.get("/openapi.json")
    assert client.app.state.session_token not in response.text


def test_authenticated_api_and_progress_work(client: TestClient) -> None:
    client.headers["Authorization"] = f"Bearer {client.app.state.session_token}"
    assert client.get("/api/auth/status").status_code == 200
    response = client.get("/api/luml/artifact/missing/progress")
    assert response.status_code == 200
    assert '"type":"not_found"' in response.text


def test_foreign_cors_origin_is_rejected(client: TestClient) -> None:
    headers = {
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    response = client.options("/api/auth/status", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    response = client.get(
        "/api/auth/status", headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 401
    assert "access-control-allow-origin" not in response.headers


def test_vite_cors_origin_is_allowed_but_needs_token(client: TestClient) -> None:
    response = client.options(
        "/api/auth/status",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert (
        client.get(
            "/api/auth/status", headers={"Origin": "http://localhost:5173"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("endpoint", ["content", "tree"])
@pytest.mark.parametrize(
    "name", ["absolute", "../marker.txt", "folder/../marker.txt", "linked/marker.txt"]
)
def test_unsafe_http_attachment_paths_return_404(
    client: TestClient, tmp_path: Path, endpoint: str, name: str
) -> None:
    tracker = experiments_handler.tracker
    experiment_id = tracker.start_experiment(name="security")
    marker = tmp_path / "marker.txt"
    marker.write_bytes(b"outside")
    attachments = tmp_path / "experiments" / experiment_id / "attachments"
    (attachments / "linked").symlink_to(tmp_path, target_is_directory=True)
    name = str(marker) if name == "absolute" else name
    client.headers["Authorization"] = f"Bearer {client.app.state.session_token}"
    path = f"/api/experiments/{experiment_id}/attachments"
    response = client.get(
        path + ("/content" if endpoint == "content" else ""),
        params={"file_path" if endpoint == "content" else "parent_path": name},
    )
    assert response.status_code == 404
    assert b"outside" not in response.content


def test_normal_http_attachments_work(client: TestClient) -> None:
    tracker = experiments_handler.tracker
    experiment_id = tracker.start_experiment(name="normal")
    tracker.log_attachment("nested/report.txt", "hello", experiment_id=experiment_id)
    client.headers["Authorization"] = f"Bearer {client.app.state.session_token}"
    path = f"/api/experiments/{experiment_id}/attachments"
    assert (
        client.get(path + "/content", params={"file_path": "nested/report.txt"}).content
        == b"hello"
    )
    assert (
        client.get(path, params={"parent_path": "nested"}).json()[0]["path"]
        == "nested/report.txt"
    )
