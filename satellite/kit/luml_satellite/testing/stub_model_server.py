import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_MANIFEST = {
    "name": "LUML end-to-end stub model",
    "version": "1.0",
    "producer_tags": ["luml.ai::tabular_monitoring:v1"],
}
_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "LUML stub model", "version": "1.0"},
    "paths": {
        "/compute": {
            "post": {
                "summary": "Compute",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "responses": {
                    "200": {
                        "description": "Stub prediction",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }
    },
}
_REFERENCE_PROFILE = {
    "profile_status": "ready",
    "task_type": "regression",
    "features": {},
}


class StubModelRequestHandler(BaseHTTPRequestHandler):
    server_version = "LUMLStubModel/1.0"

    def do_GET(self) -> None:
        if self.path == "/healthz":
            if _fixture_path() is None:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"detail": "Fixture artifact unavailable"},
                )
                return
            self._json(HTTPStatus.OK, {"status": "healthy"})
            return
        if self.path == "/manifest":
            self._json(HTTPStatus.OK, _MANIFEST)
            return
        if self.path == "/openapi.json":
            self._json(HTTPStatus.OK, _OPENAPI)
            return
        if self.path == "/reference_profile":
            self._json(HTTPStatus.OK, _REFERENCE_PROFILE)
            return
        self._json(HTTPStatus.NOT_FOUND, {"detail": "Not Found"})

    def do_POST(self) -> None:
        if self.path != "/compute":
            self._json(HTTPStatus.NOT_FOUND, {"detail": "Not Found"})
            return
        fixture_path = _fixture_path()
        if fixture_path is None:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"detail": "Fixture artifact unavailable"})
            return
        try:
            inputs = self._request_json()
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": "Invalid JSON"})
            return
        replica = os.environ.get("HOSTNAME", "stub-model")
        self._json(
            HTTPStatus.OK,
            {
                "artifact_id": os.environ["MODEL_ARTIFACT_ID"],
                "fixture": fixture,
                "inputs": inputs,
                "replica": replica,
            },
            headers={"X-Stub-Replica": replica},
        )

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _request_json(self) -> object:
        content_length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(content_length))

    def _json(
        self,
        status: HTTPStatus,
        body: object,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(encoded)


def create_stub_model_server(host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), StubModelRequestHandler)


def _fixture_path() -> Path | None:
    artifact_id = os.environ.get("MODEL_ARTIFACT_ID")
    if not artifact_id:
        return None
    candidate = Path(os.environ.get("MODEL_CACHE_DIR", "/app/models")) / artifact_id / "stub.json"
    return candidate if candidate.is_file() else None


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the LUML stub model server")
    parser.add_argument("--host", default=os.environ.get("MODEL_SERVER_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MODEL_SERVER_PORT", "8080")),
    )
    parsed = parser.parse_args(arguments)
    server = create_stub_model_server(parsed.host, parsed.port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
