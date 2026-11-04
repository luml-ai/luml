import importlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

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
    ["/..%2Fsecret.txt", "/nested%2F..%2F..%2Fsecret.txt"],
)
def test_rejects_paths_outside_root(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_rejects_absolute_path(client: TestClient, tmp_path: Path) -> None:
    response = client.get("/" + quote(str(tmp_path / "secret.txt"), safe=""))
    assert response.status_code == 404


def test_rejects_sibling_with_root_prefix(client: TestClient, tmp_path: Path) -> None:
    sibling = tmp_path / "dist-private"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("top secret")

    response = client.get("/..%2Fdist-private%2Fsecret.txt")
    assert response.status_code == 404


@pytest.mark.parametrize("link_to_directory", [False, True])
def test_rejects_symlink_outside_root(
    client: TestClient, tmp_path: Path, link_to_directory: bool
) -> None:
    link = tmp_path / "dist" / "link"
    target = tmp_path if link_to_directory else tmp_path / "secret.txt"
    link.symlink_to(target, target_is_directory=link_to_directory)

    response = client.get("/link/secret.txt" if link_to_directory else "/link")
    assert response.status_code == 404


def test_missing_file_is_404(client: TestClient) -> None:
    response = client.get("/missing.json")
    assert response.status_code == 404
