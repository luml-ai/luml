import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
import respx

from conda_manager import ModelCondaManager


@pytest.fixture
def health_server() -> Iterator[HTTPServer]:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200 if self.path == "/healthz" else 404)
            self.end_headers()

    with HTTPServer(("127.0.0.1", 0), HealthHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=2)


@pytest.mark.parametrize("port", [8080, 4321, None])
def test_worker_url_uses_loopback(port: int | None) -> None:
    manager = ModelCondaManager("env", SimpleNamespace(_exe="micromamba"), "/model")
    manager.port = port

    assert manager.worker_url == (f"http://127.0.0.1:{port}" if port else None)


@pytest.mark.parametrize("proxy", [None, "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"])
def test_health_check_reaches_local_worker_despite_proxy_environment(
    health_server: HTTPServer, monkeypatch: pytest.MonkeyPatch, proxy: str | None
) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    if proxy:
        monkeypatch.setenv(proxy, "http://127.0.0.1:0")
    manager = ModelCondaManager("env", SimpleNamespace(_exe="micromamba"), "/model")
    manager.port = health_server.server_port

    manager._wait_for_health_check(timeout=1)


@respx.mock
def test_health_check_retries_connection_errors_and_unhealthy_responses() -> None:
    manager = ModelCondaManager("env", SimpleNamespace(_exe="micromamba"), "/model")
    route = respx.get("http://127.0.0.1:8080/healthz").mock(
        side_effect=[httpx.ConnectError("starting"), httpx.Response(503), httpx.Response(200)]
    )

    with patch("conda_manager.time.sleep") as sleep:
        manager._wait_for_health_check(timeout=3)

    assert route.call_count == 3
    assert sleep.call_count == 2


@respx.mock
def test_health_check_reports_timeout_for_an_unhealthy_worker() -> None:
    manager = ModelCondaManager("env", SimpleNamespace(_exe="micromamba"), "/model")
    route = respx.get("http://127.0.0.1:8080/healthz").respond(503)

    with (
        patch("conda_manager.time.sleep"),
        pytest.raises(RuntimeError, match="Worker health check failed after 2s"),
    ):
        manager._wait_for_health_check(timeout=2)

    assert route.call_count == 2


def test_health_check_reports_worker_process_failure() -> None:
    manager = ModelCondaManager("env", SimpleNamespace(_exe="micromamba"), "/model")
    manager._error_output.append("worker could not load model")

    with (
        patch.object(manager, "process") as process,
        pytest.raises(RuntimeError, match="exited with code 1\nworker could not load model"),
    ):
        process.poll.return_value = 1
        manager._wait_for_health_check(timeout=1)
