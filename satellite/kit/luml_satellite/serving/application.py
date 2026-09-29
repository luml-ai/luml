import json
import logging
import time
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import datetime
from typing import Annotated, Any, Protocol, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException

from luml_satellite.authorization import AuthorizationVerdict, Authorizer
from luml_satellite.wire import (
    ArtifactDownload,
    DeploymentInfo,
    Healthz,
    InferenceAccessIn,
    InferenceAccessOut,
)
from luml_satellite.workload import (
    ArtifactResolver,
    ArtifactTokenError,
    InferenceOutcome,
    LocalDeployment,
    NoOpRecorder,
    Recorder,
    RecordingSession,
)

from .secrets import SecretSource, SecretUnavailable
from .transforms import (
    JsonTransform,
    RequestTransformError,
    ServingTransform,
    TransformedRequest,
)

SATELLITE_FACET = "satellite"
DEPLOYMENT_FACET = "deployment"
MONITORING_FACET = "deployment:monitoring"
INFERENCE_ACCESS_PATH = "/satellites/deployments/inference-access"
UPSTREAM_TIMEOUT_SECONDS = 45.0

_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


class DeploymentRegistry(Protocol):
    def get_deployment(self, deployment_id: str) -> LocalDeployment | None: ...

    def list_deployments(self) -> Iterable[LocalDeployment]: ...


class DeploymentNotHostedError(RuntimeError):
    detail = "Deployment not hosted"
    code = "deployment_not_hosted"


class StartingGate:
    def __init__(self, *, starting: bool = True) -> None:
        self._ready = not starting

    @property
    def ready(self) -> bool:
        return self._ready

    def mark_ready(self) -> None:
        self._ready = True

    async def require_ready(self) -> None:
        if not self._ready:
            raise HTTPException(status_code=503, detail="Satellite starting")


class _ComputeProxy:
    def __init__(
        self,
        upstream_client: httpx.AsyncClient,
        secret_source: SecretSource,
        recorder: Recorder,
        transform: ServingTransform,
        *,
        injection_body_max_bytes: int,
        upstream_timeout_seconds: float,
        clock: Callable[[], float],
        logger: logging.Logger,
    ) -> None:
        self._upstream_client = upstream_client
        self._secret_source = secret_source
        self._recorder = recorder
        self._transform = transform
        self._injection_body_max_bytes = injection_body_max_bytes
        self._upstream_timeout_seconds = upstream_timeout_seconds
        self._clock = clock
        self._logger = logger

    async def forward(self, request: Request, deployment: LocalDeployment) -> Response:
        started_at = self._clock()
        try:
            prepared = await self._transform.prepare(
                request,
                deployment,
                self._secret_source,
                record=deployment.monitoring_enabled,
                injection_body_max_bytes=self._injection_body_max_bytes,
            )
        except RequestTransformError as error:
            return await self._local_error(
                deployment,
                started_at,
                error.status_code,
                error.detail,
            )
        except SecretUnavailable as error:
            return await self._local_error(
                deployment,
                started_at,
                424,
                f"Secret unavailable: {error.attribute}",
            )

        session = await self._start_recording(deployment, prepared.inputs)
        upstream_url = deployment.upstream_url
        if upstream_url is None:
            return await self._error_response(
                session,
                started_at,
                502,
                "Upstream request failed: missing upstream URL",
            )

        headers = _request_headers(request, prepared)
        if session is not None:
            headers.update(session.upstream_headers)
        try:
            upstream_request = self._upstream_client.build_request(
                "POST",
                f"{upstream_url.rstrip('/')}/compute",
                headers=headers,
                content=prepared.content,
                timeout=self._upstream_timeout_seconds,
            )
            upstream = await self._upstream_client.send(upstream_request, stream=True)
        except httpx.TimeoutException as error:
            return await self._error_response(
                session,
                started_at,
                504,
                f"Upstream request timed out: {type(error).__name__}",
            )
        except httpx.RequestError as error:
            return await self._error_response(
                session,
                started_at,
                502,
                f"Upstream connection failed: {type(error).__name__}",
            )

        if upstream.status_code >= 400:
            try:
                body = await upstream.aread()
            except httpx.TimeoutException as error:
                await upstream.aclose()
                return await self._error_response(
                    session,
                    started_at,
                    504,
                    f"Upstream request timed out: {type(error).__name__}",
                )
            except httpx.RequestError as error:
                await upstream.aclose()
                return await self._error_response(
                    session,
                    started_at,
                    502,
                    f"Upstream connection failed: {type(error).__name__}",
                )
            detail = _upstream_error_detail(upstream, body)
            await upstream.aclose()
            return await self._error_response(
                session,
                started_at,
                upstream.status_code,
                detail,
            )

        if self._transform.streams_response:
            preserves_upstream_encoding = not upstream.is_stream_consumed
            await self._complete_recording(
                session,
                InferenceOutcome(
                    status_code=upstream.status_code,
                    latency_ms=self._latency_ms(started_at),
                ),
            )
            return StreamingResponse(
                _response_stream(upstream),
                status_code=upstream.status_code,
                headers={
                    **_response_headers(
                        upstream.headers,
                        streaming=preserves_upstream_encoding,
                    ),
                    **_event_headers(session),
                },
                background=BackgroundTask(upstream.aclose),
            )

        try:
            body = await upstream.aread()
        except httpx.TimeoutException as error:
            await upstream.aclose()
            return await self._error_response(
                session,
                started_at,
                504,
                f"Upstream request timed out: {type(error).__name__}",
            )
        except httpx.RequestError as error:
            await upstream.aclose()
            return await self._error_response(
                session,
                started_at,
                502,
                f"Upstream connection failed: {type(error).__name__}",
            )
        await upstream.aclose()
        content_type = upstream.headers.get("content-type")
        transformed = self._transform.transform_response(body, content_type)
        output = self._transform.recorded_output(
            transformed,
            content_type,
            deployment.recording_policy.body_max_bytes,
        )
        await self._complete_recording(
            session,
            InferenceOutcome(
                status_code=upstream.status_code,
                latency_ms=self._latency_ms(started_at),
                output=output,
            ),
        )
        return Response(
            transformed,
            status_code=upstream.status_code,
            headers={
                **_response_headers(upstream.headers, streaming=False),
                **_event_headers(session),
            },
            media_type=None,
        )

    async def _local_error(
        self,
        deployment: LocalDeployment,
        started_at: float,
        status_code: int,
        detail: str,
    ) -> JSONResponse:
        session = await self._start_recording(deployment, None)
        return await self._error_response(session, started_at, status_code, detail)

    async def _error_response(
        self,
        session: RecordingSession | None,
        started_at: float,
        status_code: int,
        detail: str,
    ) -> JSONResponse:
        await self._complete_recording(
            session,
            InferenceOutcome(
                status_code=status_code,
                latency_ms=self._latency_ms(started_at),
                error=detail,
            ),
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
            headers=_event_headers(session),
        )

    async def _start_recording(
        self,
        deployment: LocalDeployment,
        inputs: object | None,
    ) -> RecordingSession | None:
        if not deployment.monitoring_enabled:
            return None
        try:
            return await self._recorder.start(
                deployment.deployment_id,
                inputs,
                deployment.recording_policy,
            )
        except Exception:
            self._logger.warning("failed to start inference recording", exc_info=True)
            return None

    async def _complete_recording(
        self,
        session: RecordingSession | None,
        outcome: InferenceOutcome,
    ) -> None:
        if session is None:
            return
        try:
            await session.complete(outcome)
        except Exception:
            self._logger.warning("failed to complete inference recording", exc_info=True)

    def _latency_ms(self, started_at: float) -> float:
        return max(0.0, (self._clock() - started_at) * 1000)


def create_serving_application(
    registry: DeploymentRegistry,
    authorizer: Authorizer,
    secret_source: SecretSource,
    *,
    recorder: Recorder | None = None,
    transform: ServingTransform | None = None,
    upstream_client: httpx.AsyncClient | None = None,
    starting_gate: StartingGate | None = None,
    single_deployment_id: str | None = None,
    not_hosted: bool = False,
    injection_body_max_bytes: int = 16_777_216,
    upstream_timeout_seconds: float = UPSTREAM_TIMEOUT_SECONDS,
    authorization_unavailable_status_code: int = 502,
    authorization_unavailable_detail: str = "Authorization failed",
    last_monitored_at: Callable[[str], datetime | None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    logger: logging.Logger | None = None,
) -> FastAPI:
    if injection_body_max_bytes <= 0:
        raise ValueError("injection_body_max_bytes must be greater than zero")
    if upstream_timeout_seconds <= 0:
        raise ValueError("upstream_timeout_seconds must be greater than zero")
    if not 400 <= authorization_unavailable_status_code <= 599:
        raise ValueError("authorization_unavailable_status_code must be an error status")

    active_gate = starting_gate or StartingGate()
    client = upstream_client or httpx.AsyncClient(timeout=upstream_timeout_seconds)
    active_logger = logger or logging.getLogger("luml_satellite.serving")
    proxy = _ComputeProxy(
        client,
        secret_source,
        recorder or NoOpRecorder(),
        transform or JsonTransform(),
        injection_body_max_bytes=injection_body_max_bytes,
        upstream_timeout_seconds=upstream_timeout_seconds,
        clock=clock,
        logger=active_logger,
    )
    application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    application.state.serving_upstream_client = client
    application.state.starting_gate = active_gate
    security = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> None:
        if credentials is None:
            raise HTTPException(status_code=403, detail="Not authenticated")
        verdict = await authorizer.authorize(credentials.credentials)
        if verdict is AuthorizationVerdict.DENIED:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if verdict is AuthorizationVerdict.UNAVAILABLE:
            raise HTTPException(
                status_code=authorization_unavailable_status_code,
                detail=authorization_unavailable_detail,
            )

    def hosted(deployment_id: str) -> LocalDeployment:
        if single_deployment_id is not None and deployment_id != single_deployment_id:
            raise DeploymentNotHostedError
        deployment = registry.get_deployment(deployment_id)
        if deployment is None:
            raise DeploymentNotHostedError
        return deployment

    @application.exception_handler(DeploymentNotHostedError)
    async def deployment_not_hosted(
        request: Request,
        error: DeploymentNotHostedError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": error.code},
        )

    @application.exception_handler(404)
    async def unknown_route(request: Request, error: StarletteHTTPException) -> Response:
        if request.url.path.startswith("/monitoring") or request.scope.get("route") is not None:
            return await http_exception_handler(request, error)
        return JSONResponse(
            status_code=404,
            content={"detail": error.detail, "code": "unknown_route"},
            headers=error.headers,
        )

    @application.post(
        INFERENCE_ACCESS_PATH,
        response_model=InferenceAccessOut,
        tags=[SATELLITE_FACET],
        summary="Check inference access",
        description="Check whether the supplied API key may call inference on this Satellite.",
        dependencies=[Depends(verify_token)],
    )
    async def authorize_inference_access(body: InferenceAccessIn) -> InferenceAccessOut:
        verdict = await authorizer.authorize(body.api_key)
        if verdict is AuthorizationVerdict.UNAVAILABLE:
            raise HTTPException(
                status_code=authorization_unavailable_status_code,
                detail=authorization_unavailable_detail,
            )
        return InferenceAccessOut(authorized=verdict is AuthorizationVerdict.ALLOWED)

    @application.get(
        "/healthz",
        response_model=Healthz,
        tags=[SATELLITE_FACET],
        summary="Check Satellite health",
        description="Report whether the Satellite Agent is running.",
        dependencies=[Depends(verify_token)],
    )
    async def healthz() -> Healthz:
        return Healthz()

    @application.get(
        "/deployments",
        response_model=list[DeploymentInfo],
        tags=[DEPLOYMENT_FACET],
        summary="List hosted deployments",
        description="List active deployments hosted by this Satellite and their monitoring state.",
        dependencies=[Depends(verify_token), Depends(active_gate.require_ready)],
    )
    async def deployments() -> list[DeploymentInfo]:
        records = registry.list_deployments()
        return [
            DeploymentInfo(
                deployment_id=deployment.deployment_id,
                name=deployment.metadata.name,
                status=deployment.metadata.status,
                monitoring_mode="full" if deployment.monitoring_enabled else "off",
                last_monitored_at=(
                    last_monitored_at(deployment.deployment_id)
                    if last_monitored_at is not None
                    else None
                ),
            )
            for deployment in records
            if single_deployment_id is None or deployment.deployment_id == single_deployment_id
        ]

    @application.post(
        "/deployments/{deployment_id}/compute",
        response_model=None,
        tags=[DEPLOYMENT_FACET],
        summary="Run deployment inference",
        description="Run inference using the model served by the selected deployment.",
        dependencies=[Depends(verify_token), Depends(active_gate.require_ready)],
    )
    async def compute(deployment_id: str, request: Request) -> Response:
        if not_hosted:
            raise DeploymentNotHostedError
        return await proxy.forward(request, hosted(deployment_id))

    @application.get(
        "/deployments/{deployment_id}/openapi.json",
        tags=[DEPLOYMENT_FACET],
        summary="Get deployment schema",
        description="Return the OpenAPI schema for the selected deployment.",
        dependencies=[Depends(verify_token), Depends(active_gate.require_ready)],
    )
    async def deployment_openapi(deployment_id: str) -> JSONResponse:
        schema = hosted(deployment_id).openapi_schema
        return JSONResponse(cast(Any, schema))

    @application.get("/livez", include_in_schema=False)
    async def livez() -> dict[str, str]:
        return {"status": "healthy"}

    @application.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(verify_token)],
    )
    async def openapi_json() -> JSONResponse:
        return JSONResponse(application.openapi())

    @application.get("/docs", include_in_schema=False, dependencies=[Depends(verify_token)])
    async def swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Satellite Agent API - Swagger UI",
        )

    @application.get("/redoc", include_in_schema=False, dependencies=[Depends(verify_token)])
    async def redoc() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="Satellite Agent API - ReDoc",
        )

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = get_openapi(
            title="Satellite Agent API",
            version="1.0.0",
            description="API for managing model deployments and inference",
            routes=application.routes,
            tags=[
                {
                    "name": SATELLITE_FACET,
                    "description": "Operations about the Satellite itself.",
                },
                {
                    "name": DEPLOYMENT_FACET,
                    "description": "Operations for deployments hosted by the Satellite.",
                },
                {
                    "name": MONITORING_FACET,
                    "description": "Monitoring operations for one hosted deployment.",
                },
            ],
        )
        _restore_compute_contract(schema)
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]
    return application


def create_artifact_router(resolver: ArtifactResolver) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/satellites/deployments/{deployment_id}/artifact",
        response_model=ArtifactDownload,
        include_in_schema=False,
    )
    async def artifact_download(
        deployment_id: UUID,
        x_artifact_token: Annotated[str | None, Header()] = None,
    ) -> ArtifactDownload:
        try:
            return await resolver.resolve_download(str(deployment_id), x_artifact_token)
        except ArtifactTokenError as error:
            raise HTTPException(status_code=403, detail="Invalid artifact token") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Unknown deployment") from error
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"Could not resolve artifact: {error}",
            ) from error

    return router


def create_internal_application(resolver: ArtifactResolver) -> FastAPI:
    application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    application.include_router(create_artifact_router(resolver))
    return application


def _request_headers(request: Request, transformed: TransformedRequest) -> dict[str, str]:
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in _HOP_BY_HOP_HEADERS and name.lower() not in {"authorization", "host"}
    }
    if transformed.content_changed:
        headers.pop("content-length", None)
    headers.update(transformed.headers)
    return headers


def _response_headers(headers: httpx.Headers, *, streaming: bool) -> dict[str, str]:
    excluded = {*_HOP_BY_HOP_HEADERS, "x-event-id"}
    if not streaming:
        excluded.update({"content-encoding", "content-length"})
    return {name: value for name, value in headers.items() if name.lower() not in excluded}


def _event_headers(session: RecordingSession | None) -> dict[str, str]:
    if session is None or session.event_id is None:
        return {}
    return {"X-Event-Id": session.event_id}


async def _response_stream(response: httpx.Response) -> AsyncIterator[bytes]:
    if response.is_stream_consumed:
        yield response.content
        return
    async for chunk in response.aiter_raw():
        yield chunk


def _upstream_error_detail(response: httpx.Response, body: bytes) -> str:
    try:
        payload: object = json.loads(body)
    except json.JSONDecodeError, UnicodeDecodeError:
        text = body.decode(errors="replace")
        return text or response.reason_phrase
    if isinstance(payload, dict) and "error" in payload:
        return str(payload["error"])
    return json.dumps(payload)


def _restore_compute_contract(schema: dict[str, Any]) -> None:
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return
    path = paths.get("/deployments/{deployment_id}/compute")
    if not isinstance(path, dict):
        return
    operation = path.get("post")
    if not isinstance(operation, dict):
        return
    operation["requestBody"] = {
        "content": {
            "application/json": {
                "schema": {
                    "additionalProperties": True,
                    "title": "Body",
                    "type": "object",
                }
            }
        },
        "required": True,
    }
    operation["responses"] = {
        "200": {
            "content": {
                "application/json": {
                    "schema": {
                        "additionalProperties": True,
                        "title": "Response Compute Deployments  Deployment Id  Compute Post",
                        "type": "object",
                    }
                }
            },
            "description": "Successful Response",
        },
        "422": {
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}
            },
            "description": "Validation Error",
        },
    }
