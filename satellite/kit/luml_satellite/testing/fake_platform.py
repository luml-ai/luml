import argparse
import base64
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import parse_qs
from uuid import UUID

import httpx

from luml_satellite._version import SATELLITE_API_VERSION
from luml_satellite.wire.contract import CLIENT_OPERATIONS

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

_TASK_STATUS_PATH = re.compile(r"^/satellites/v1/tasks/([^/]+)/status$")
_DEPLOYMENT_STATUS_PATH = re.compile(r"^/satellites/v1/deployments/([^/]+)/status$")
_DEPLOYMENT_PATH = re.compile(r"^/satellites/v1/deployments/([^/]+)$")
_SECRET_PATH = re.compile(r"^/satellites/v1/secrets/([^/]+)$")
_ARTIFACT_DOWNLOAD_PATH = re.compile(r"^/satellites/v1/artifacts/([^/]+)/download-url$")
_ARTIFACT_PATH = re.compile(r"^/satellites/v1/artifacts/([^/]+)$")
_LEGACY_ARTIFACT_DOWNLOAD_PATH = re.compile(
    r"^/satellites/v1/model_artifacts/([^/]+)/download-url$"
)
_LEGACY_ARTIFACT_PATH = re.compile(r"^/satellites/v1/model_artifacts/([^/]+)$")
_ARTIFACT_CONTENT_PATH = re.compile(r"^/__fake__/artifacts/([^/]+)$")


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    query: dict[str, list[str]]
    body: object = None


@dataclass(frozen=True)
class RecordedTransition:
    resource: Literal["deployment", "task"]
    resource_id: str
    previous_status: str | None
    status: str
    body: dict[str, Any]


@dataclass(frozen=True)
class FakeArtifact:
    metadata: dict[str, Any]
    content: bytes


@dataclass(frozen=True)
class _Response:
    status_code: int
    body: bytes = b""
    content_type: str | None = "application/json"
    headers: tuple[tuple[bytes, bytes], ...] = ()


@dataclass
class FakePlatform:
    token: str = "test-token"
    legacy: bool = False
    api_version: int = SATELLITE_API_VERSION
    satellite_id: str = "00000000-0000-0000-0000-000000000001"
    orbit_id: str = "00000000-0000-0000-0000-000000000002"
    deployments: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    secrets: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, FakeArtifact] = field(default_factory=dict)
    allowed_api_keys: set[str] = field(default_factory=set)
    monitoring_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)
    transitions: list[RecordedTransition] = field(default_factory=list)
    deployment_updates: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    pairing_error: tuple[int, object] | None = None
    contract_error: tuple[int, object] | None = None
    refused_deployment_transitions: set[tuple[str, str]] = field(default_factory=set)
    refused_task_transitions: set[tuple[str, str]] = field(default_factory=set)
    contract_openapi: dict[str, Any] = field(default_factory=lambda: default_contract_openapi())

    @property
    def transport(self) -> httpx.ASGITransport:
        return httpx.ASGITransport(app=self)

    @property
    def deployment_transitions(self) -> list[RecordedTransition]:
        return [item for item in self.transitions if item.resource == "deployment"]

    @property
    def task_transitions(self) -> list[RecordedTransition]:
        return [item for item in self.transitions if item.resource == "task"]

    def add_deployment(self, deployment: Mapping[str, Any]) -> None:
        record = _json_mapping(deployment)
        self.deployments[str(record["id"])] = record

    def add_task(self, task: Mapping[str, Any]) -> None:
        record = _json_mapping(task)
        self.tasks[str(record["id"])] = record

    def add_secret(self, secret_id: str | UUID, name: str, value: str) -> None:
        self.secrets[str(secret_id)] = {"id": str(secret_id), "name": name, "value": value}

    def add_artifact(
        self,
        artifact_id: str | UUID,
        content: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        identifier = str(artifact_id)
        artifact_metadata = {"id": identifier, "name": "fixture.tar.gz"}
        if metadata is not None:
            artifact_metadata.update(_json_mapping(metadata))
        self.artifacts[identifier] = FakeArtifact(artifact_metadata, content)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope_type != "http":
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", "/"))
        query = parse_qs(bytes(scope.get("query_string", b"")).decode())
        raw_body = await _read_body(receive)
        body = _decode_json(raw_body)
        self.requests.append(RecordedRequest(method, path, query, body))
        response = self._dispatch(scope, method, path, query, body)
        await _send_response(send, response)

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            message_type = message.get("type")
            if message_type == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message_type == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    def _dispatch(
        self,
        scope: Scope,
        method: str,
        path: str,
        query: dict[str, list[str]],
        body: object,
    ) -> _Response:
        if method == "GET" and path == "/satellites/v1/contract":
            return self._contract_response()

        content_match = _ARTIFACT_CONTENT_PATH.fullmatch(path)
        if method == "GET" and content_match:
            return self._artifact_content(content_match.group(1))

        if not self._authenticated(scope):
            return _json_response(401, {"detail": "Authentication error"})

        if method == "POST" and path == "/satellites/v1/pair":
            return self._pair(body)
        if method == "GET" and path == "/satellites/v1/tasks":
            return self._list_tasks(query)

        task_match = _TASK_STATUS_PATH.fullmatch(path)
        if method == "POST" and task_match:
            return self._update_task(task_match.group(1), body)

        if method == "GET" and path == "/satellites/v1/deployments":
            return _json_response(200, list(self.deployments.values()))
        if method == "POST" and path == "/satellites/v1/deployments/inference-access":
            api_key = body.get("api_key") if isinstance(body, dict) else None
            return _json_response(200, {"authorized": api_key in self.allowed_api_keys})

        deployment_status_match = _DEPLOYMENT_STATUS_PATH.fullmatch(path)
        if method == "PATCH" and deployment_status_match:
            return self._update_deployment(deployment_status_match.group(1), body)

        deployment_match = _DEPLOYMENT_PATH.fullmatch(path)
        if deployment_match:
            deployment_id = deployment_match.group(1)
            if method == "GET":
                return self._get(self.deployments, deployment_id, "Deployment not found")
            if method == "PATCH":
                return self._update_deployment(deployment_id, body)
            if method == "DELETE":
                return self._delete_deployment(deployment_id)

        if method == "GET" and path == "/satellites/v1/secrets":
            return _json_response(200, list(self.secrets.values()))
        secret_match = _SECRET_PATH.fullmatch(path)
        if method == "GET" and secret_match:
            return self._get(self.secrets, secret_match.group(1), "Secret not found")

        if method == "POST" and path == "/satellites/v1/monitoring/introspect":
            token = body.get("token") if isinstance(body, dict) else None
            result = self.monitoring_tokens.get(str(token), {"active": False, "claims": None})
            return _json_response(200, result)

        artifact_download_match = _ARTIFACT_DOWNLOAD_PATH.fullmatch(path)
        if method == "GET" and artifact_download_match:
            return self._artifact_url(scope, artifact_download_match.group(1))
        artifact_match = _ARTIFACT_PATH.fullmatch(path)
        if method == "GET" and artifact_match:
            return self._artifact(scope, artifact_match.group(1), legacy=False)

        legacy_download_match = _LEGACY_ARTIFACT_DOWNLOAD_PATH.fullmatch(path)
        if method == "GET" and legacy_download_match:
            return self._artifact_url(scope, legacy_download_match.group(1))
        legacy_artifact_match = _LEGACY_ARTIFACT_PATH.fullmatch(path)
        if method == "GET" and legacy_artifact_match:
            return self._artifact(scope, legacy_artifact_match.group(1), legacy=True)

        return _json_response(404, {"detail": "Not Found"})

    def _authenticated(self, scope: Scope) -> bool:
        headers = {
            bytes(name).decode().lower(): bytes(value).decode()
            for name, value in scope.get("headers", [])
        }
        return headers.get("authorization") == f"Bearer {self.token}"

    def _contract_response(self) -> _Response:
        if self.legacy:
            return _json_response(404, {"detail": "Not Found"})
        if self.contract_error is not None:
            status_code, detail = self.contract_error
            return _json_response(status_code, {"detail": detail})
        return _json_response(
            200,
            {"api_version": self.api_version, "openapi": self.contract_openapi},
        )

    def _pair(self, body: object) -> _Response:
        if self.pairing_error is not None:
            status_code, detail = self.pairing_error
            return _json_response(status_code, {"detail": detail})
        if not isinstance(body, dict):
            return _validation_error("body")
        if self.legacy and not body.get("base_url"):
            return _validation_error("base_url")
        capabilities = body.get("capabilities")
        if not isinstance(capabilities, dict):
            return _validation_error("capabilities")

        stored_capabilities = (
            _legacy_capabilities(capabilities) if self.legacy else _json_mapping(capabilities)
        )
        now = datetime.now(UTC).isoformat()
        response: dict[str, Any] = {
            "id": self.satellite_id,
            "orbit_id": self.orbit_id,
            "name": "Fake satellite",
            "description": None,
            "base_url": body.get("base_url"),
            "paired": True,
            "capabilities": stored_capabilities,
            "slug": body.get("slug"),
            "created_at": now,
            "updated_at": now,
            "last_seen_at": now,
        }
        if not self.legacy:
            response["kit_info"] = body.get("kit")
        return _json_response(200, response)

    def _list_tasks(self, query: dict[str, list[str]]) -> _Response:
        statuses = query.get("status")
        tasks = list(self.tasks.values())
        if statuses:
            tasks = [task for task in tasks if task.get("status") == statuses[0]]
        return _json_response(200, tasks)

    def _update_task(self, task_id: str, body: object) -> _Response:
        record = self.tasks.get(task_id)
        if record is None:
            return _json_response(404, {"detail": "Task not found"})
        if not isinstance(body, dict) or not isinstance(body.get("status"), str):
            return _validation_error("status")
        status = body["status"]
        previous = str(record.get("status")) if record.get("status") is not None else None
        if previous is not None and (previous, status) in self.refused_task_transitions:
            return _json_response(409, {"detail": "Task transition refused"})
        record.update(_json_mapping(body))
        self.transitions.append(RecordedTransition("task", task_id, previous, status, body.copy()))
        return _json_response(200, record)

    def _update_deployment(self, deployment_id: str, body: object) -> _Response:
        record = self.deployments.get(deployment_id)
        if record is None:
            return _json_response(404, {"detail": "Deployment not found"})
        if not isinstance(body, dict):
            return _validation_error("body")
        status = body.get("status")
        previous = str(record.get("status")) if record.get("status") is not None else None
        if isinstance(status, str):
            if previous is not None and (previous, status) in self.refused_deployment_transitions:
                return _json_response(409, {"detail": "Deployment transition refused"})
            self.transitions.append(
                RecordedTransition("deployment", deployment_id, previous, status, body.copy())
            )
        record.update(_json_mapping(body))
        self.deployment_updates.append((deployment_id, body.copy()))
        return _json_response(200, record)

    def _delete_deployment(self, deployment_id: str) -> _Response:
        if deployment_id not in self.deployments:
            return _json_response(404, {"detail": "Deployment not found"})
        del self.deployments[deployment_id]
        return _Response(204, content_type=None)

    def _artifact_url(self, scope: Scope, artifact_id: str) -> _Response:
        if artifact_id not in self.artifacts:
            return _json_response(404, {"detail": "Artifact not found"})
        return _json_response(200, {"url": self._content_url(scope, artifact_id)})

    def _artifact(self, scope: Scope, artifact_id: str, *, legacy: bool) -> _Response:
        artifact = self.artifacts.get(artifact_id)
        if artifact is None:
            return _json_response(404, {"detail": "Artifact not found"})
        body = {
            "artifact": artifact.metadata,
            "url": self._content_url(scope, artifact_id),
        }
        if legacy:
            body["model"] = artifact.metadata
        return _json_response(200, body)

    def _artifact_content(self, artifact_id: str) -> _Response:
        artifact = self.artifacts.get(artifact_id)
        if artifact is None:
            return _json_response(404, {"detail": "Artifact not found"})
        return _Response(200, artifact.content, "application/octet-stream")

    def _content_url(self, scope: Scope, artifact_id: str) -> str:
        headers = {
            bytes(name).decode().lower(): bytes(value).decode()
            for name, value in scope.get("headers", [])
        }
        host = headers.get("host", "testserver")
        scheme = str(scope.get("scheme", "http"))
        return f"{scheme}://{host}/__fake__/artifacts/{artifact_id}"

    @staticmethod
    def _get(
        records: dict[str, dict[str, Any]],
        resource_id: str,
        detail: str,
    ) -> _Response:
        record = records.get(resource_id)
        if record is None:
            return _json_response(404, {"detail": detail})
        return _json_response(200, record)

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> FakePlatform:
        platform = cls(
            token=str(state.get("token", "test-token")),
            legacy=bool(state.get("legacy", False)),
            api_version=int(state.get("api_version", SATELLITE_API_VERSION)),
        )
        for deployment in _mapping_items(state.get("deployments")):
            platform.add_deployment(deployment)
        for task in _mapping_items(state.get("tasks")):
            platform.add_task(task)
        for secret in _mapping_items(state.get("secrets")):
            platform.add_secret(str(secret["id"]), str(secret["name"]), str(secret["value"]))
        for artifact in _mapping_items(state.get("artifacts")):
            content = base64.b64decode(str(artifact.get("content_base64", "")))
            metadata = artifact.get("metadata")
            platform.add_artifact(
                str(artifact["id"]),
                content,
                metadata if isinstance(metadata, Mapping) else None,
            )
        api_keys = state.get("allowed_api_keys", [])
        if isinstance(api_keys, list):
            platform.allowed_api_keys.update(str(item) for item in api_keys)
        monitoring_tokens = state.get("monitoring_tokens")
        if isinstance(monitoring_tokens, Mapping):
            platform.monitoring_tokens.update(
                {
                    str(token): _json_mapping(value)
                    for token, value in monitoring_tokens.items()
                    if isinstance(value, Mapping)
                }
            )
        return platform


def default_contract_openapi() -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {}
    for operation in CLIENT_OPERATIONS:
        paths.setdefault(operation.path, {})[operation.method] = {
            "responses": {"200": {"description": "Success"}}
        }
    paths["/satellites/v1/model_artifacts/{model_artifact_id}"] = {
        "get": {"deprecated": True, "responses": {"200": {"description": "Success"}}}
    }
    paths["/satellites/v1/model_artifacts/{model_artifact_id}/download-url"] = {
        "get": {"deprecated": True, "responses": {"200": {"description": "Success"}}}
    }
    return {"openapi": "3.1.0", "paths": paths}


def _legacy_capabilities(capabilities: Mapping[str, Any]) -> dict[str, Any]:
    known_fields = {
        "deploy": {
            "version",
            "api_versions",
            "facets",
            "supported_variants",
            "supported_tags_combinations",
            "extra_fields_form_spec",
        },
        "monitoring": {"version", "api_versions", "facets", "features"},
    }
    result: dict[str, Any] = {}
    for name, declaration in capabilities.items():
        if not isinstance(declaration, Mapping):
            continue
        allowed = known_fields.get(str(name))
        if allowed is None:
            continue
        result[str(name)] = {
            str(key): _jsonable(value) for key, value in declaration.items() if str(key) in allowed
        }
    return result


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _json_mapping(value: Mapping[Any, Any]) -> dict[str, Any]:
    return {str(key): _jsonable(item) for key, item in value.items()}


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return _json_mapping(value)
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime | UUID):
        return str(value)
    return value


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        chunks.append(bytes(message.get("body", b"")))
        if not message.get("more_body", False):
            return b"".join(chunks)


def _decode_json(body: bytes) -> object:
    if not body:
        return None
    try:
        return cast(object, json.loads(body))
    except json.JSONDecodeError:
        return None


def _json_response(status_code: int, value: object) -> _Response:
    return _Response(status_code, json.dumps(value, default=str).encode())


def _validation_error(field_name: str) -> _Response:
    return _json_response(
        422,
        {
            "detail": [
                {
                    "type": "missing",
                    "loc": ["body", field_name],
                    "msg": "Field required",
                }
            ]
        },
    )


async def _send_response(send: Send, response: _Response) -> None:
    headers = list(response.headers)
    if response.content_type is not None:
        headers.append((b"content-type", response.content_type.encode()))
    headers.append((b"content-length", str(len(response.body)).encode()))
    await send(
        {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": response.body})


def _load_state(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("fake platform state must be a JSON object")
    return cast(dict[str, Any], value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LUML fake platform")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--token", default=None)
    parser.add_argument("--state", type=Path)
    arguments = parser.parse_args()

    state = _load_state(arguments.state)
    configured_token = arguments.token or os.environ.get("SATELLITE_TOKEN")
    if configured_token is not None:
        state["token"] = configured_token
    platform = FakePlatform.from_state(state)

    import uvicorn

    uvicorn.run(platform, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
