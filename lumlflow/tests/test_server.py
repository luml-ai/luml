from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lumlflow.server import SPAStaticFiles
from lumlflow.service import AppService


@pytest.fixture()
def static_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html><body>SPA</body></html>")
    assets = static / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')")
    return static


@pytest.fixture()
def app_with_static(static_dir: Path) -> FastAPI:
    app = AppService()
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")
    return app


@pytest.fixture()
def client(app_with_static: FastAPI) -> TestClient:
    return TestClient(app_with_static)


def test_get_api_routes_not_shadowed_by_spa(client: TestClient) -> None:
    response = client.get("/api/auth/status")
    assert response.headers["content-type"] == "application/json"


def test_post_api_routes_not_shadowed_by_spa(client: TestClient) -> None:
    response = client.post("/api/auth/api-key", json={"api_key": "test"})
    content_type = response.headers.get("content-type", "")
    assert "text/html" not in content_type


def test_spa_fallback_serves_index(client: TestClient) -> None:
    response = client.get("/experiments/some-group")
    assert response.status_code == 200
    assert "SPA" in response.text


def test_static_assets_served(client: TestClient) -> None:
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_root_serves_index(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "SPA" in response.text


def test_nonexistent_path_falls_back_to_index(client: TestClient) -> None:
    response = client.get("/some/random/path")
    assert response.status_code == 200
    assert "SPA" in response.text
