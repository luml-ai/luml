import importlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVER_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    static_root = tmp_path / "dist"
    static_root.mkdir()
    (static_root / "jupyter-lite.json").write_text(
        json.dumps({"jupyter-config-data": {}})
    )
    (static_root / "index.html").write_text("<html></html>")
    (tmp_path / "secret.txt").write_text("top secret")

    monkeypatch.chdir(static_root)
    monkeypatch.syspath_prepend(str(SERVER_DIR))
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    yield TestClient(server.app)
    sys.modules.pop("server", None)


def test_serves_file_inside_root(client: TestClient) -> None:
    response = client.get("/index.html")
    assert response.content == b"<html></html>"


def test_serves_config_with_storage_name(client: TestClient) -> None:
    response = client.get(
        "/jupyter-lite.json", headers={"referer": "http://x/?instanceId=abc"}
    )
    assert response.json()["jupyter-config-data"]["contentsStorageName"] == "abc"


@pytest.mark.parametrize(
    "path",
    ["/%2Fetc%2Fpasswd", "/..%2Fsecret.txt"],
)
def test_rejects_paths_outside_root(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_missing_file_is_404(client: TestClient) -> None:
    response = client.get("/missing.json")
    assert response.status_code == 404


def test_host_header_does_not_change_file_lookup(client: TestClient) -> None:
    response = client.get("/index.html", headers={"host": "untrusted.example"})
    assert response.status_code == 200
    assert response.content == b"<html></html>"


def test_range_header_is_ignored(client: TestClient) -> None:
    response = client.get("/index.html", headers={"range": "bytes=0-1"})
    assert response.status_code == 200
    assert response.content == b"<html></html>"


@pytest.mark.parametrize("method", ["POST", "DELETE", "__init__"])
def test_unsupported_methods_are_rejected(client: TestClient, method: str) -> None:
    response = client.request(method, "/index.html")
    assert response.status_code == 405
