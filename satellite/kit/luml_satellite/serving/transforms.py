import json
from collections.abc import AsyncIterable, AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from fastapi import Request

from luml_satellite.workload import LocalDeployment

from .secrets import SecretSource, SecretUnavailable

_STREAM_CHUNK_BYTES = 1024 * 1024


class RequestTransformError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class TransformedRequest:
    content: bytes | AsyncIterable[bytes]
    inputs: object | None
    content_changed: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)


class ServingTransform(Protocol):
    @property
    def streams_response(self) -> bool: ...

    async def prepare(
        self,
        request: Request,
        deployment: LocalDeployment,
        secret_source: SecretSource,
        *,
        record: bool,
        injection_body_max_bytes: int,
    ) -> TransformedRequest: ...

    def transform_response(self, body: bytes, content_type: str | None) -> bytes: ...

    def recorded_output(
        self,
        body: bytes,
        content_type: str | None,
        body_max_bytes: int,
    ) -> object | None: ...


class JsonTransform:
    @property
    def streams_response(self) -> bool:
        return False

    async def prepare(
        self,
        request: Request,
        deployment: LocalDeployment,
        secret_source: SecretSource,
        *,
        record: bool,
        injection_body_max_bytes: int,
    ) -> TransformedRequest:
        secret_references = deployment.dynamic_attributes_secrets
        if not record and not secret_references:
            return TransformedRequest(request.stream(), None)

        limit = (
            injection_body_max_bytes
            if secret_references
            else deployment.recording_policy.body_max_bytes
        )
        body, overflow = await _read_bounded(request, limit)
        if overflow is not None:
            if secret_references:
                raise RequestTransformError(413, "Request body exceeds the injection limit")
            return TransformedRequest(overflow, None)

        payload = _json_object(body)
        inputs = _safe_inputs(payload, secret_references) if record else None
        dynamic_attributes = payload.get("dynamic_attributes") or {}
        if not isinstance(dynamic_attributes, dict):
            raise RequestTransformError(422, "Request body must contain JSON object attributes")

        missing = {
            attribute: secret_id
            for attribute, secret_id in secret_references.items()
            if attribute not in dynamic_attributes
        }
        if missing:
            try:
                values = await secret_source.resolve(deployment.deployment_id, missing)
            except SecretUnavailable:
                raise
            except Exception as error:
                raise SecretUnavailable(next(iter(missing))) from error
            dynamic_attributes = {**dynamic_attributes, **values}
        payload["dynamic_attributes"] = dynamic_attributes
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        return TransformedRequest(
            encoded,
            inputs,
            content_changed=True,
            headers={"content-type": "application/json"},
        )

    def transform_response(self, body: bytes, content_type: str | None) -> bytes:
        del content_type
        return body

    def recorded_output(
        self,
        body: bytes,
        content_type: str | None,
        body_max_bytes: int,
    ) -> object | None:
        del content_type
        if len(body) > body_max_bytes:
            return None
        try:
            return cast(object, json.loads(body))
        except json.JSONDecodeError, UnicodeDecodeError:
            return None


class PassThroughTransform:
    @property
    def streams_response(self) -> bool:
        return True

    async def prepare(
        self,
        request: Request,
        deployment: LocalDeployment,
        secret_source: SecretSource,
        *,
        record: bool,
        injection_body_max_bytes: int,
    ) -> TransformedRequest:
        del deployment, secret_source, record, injection_body_max_bytes
        return TransformedRequest(_chunked_stream(request.stream()), None)

    def transform_response(self, body: bytes, content_type: str | None) -> bytes:
        del content_type
        return body

    def recorded_output(
        self,
        body: bytes,
        content_type: str | None,
        body_max_bytes: int,
    ) -> None:
        del body, content_type, body_max_bytes
        return None


def _json_object(body: bytes) -> dict[str, Any]:
    try:
        payload: object = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RequestTransformError(422, "Request body must be valid JSON") from error
    if not isinstance(payload, dict):
        raise RequestTransformError(422, "Request body must be a JSON object")
    return payload


def _safe_inputs(
    body: Mapping[str, Any],
    secret_references: Mapping[str, str],
) -> dict[str, Any] | None:
    safe: dict[str, Any] = {}
    if body.get("inputs") is not None:
        safe["inputs"] = body["inputs"]
    dynamic_attributes = body.get("dynamic_attributes")
    if isinstance(dynamic_attributes, dict):
        safe["dynamic_attributes"] = {
            key: value for key, value in dynamic_attributes.items() if key not in secret_references
        }
    return safe or None


async def _read_bounded(
    request: Request,
    limit: int,
) -> tuple[bytes, AsyncIterable[bytes] | None]:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > limit:
                return b"", request.stream()
        except ValueError:
            pass

    stream = request.stream()
    chunks: list[bytes] = []
    size = 0
    async for chunk in stream:
        chunks.append(chunk)
        size += len(chunk)
        if size > limit:
            return b"", _prefixed_stream(chunks, stream)
    return b"".join(chunks), None


async def _prefixed_stream(
    chunks: list[bytes],
    remainder: AsyncIterator[bytes],
) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk
    async for chunk in remainder:
        yield chunk


async def _chunked_stream(stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    async for chunk in stream:
        for offset in range(0, len(chunk), _STREAM_CHUNK_BYTES):
            yield chunk[offset : offset + _STREAM_CHUNK_BYTES]
