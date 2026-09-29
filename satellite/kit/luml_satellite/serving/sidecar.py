import asyncio
import copy
import hmac
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from typing import Annotated, Any, Protocol, Self, cast

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from luml_satellite.convergence import ModelDescription
from luml_satellite.workload import (
    LocalDeployment,
    NoOpRecorder,
    Recorder,
    RecordingPolicy,
)

from .application import StartingGate, create_serving_application
from .companion import (
    CompanionApi,
    CompanionAuthorizer,
    CompanionClient,
    CompanionMetadata,
    CompanionSecretSource,
    CompanionUnavailableError,
)
from .placement import gate_reference_profile, without_secret_attributes


class SidecarConfiguration(BaseSettings):
    DEPLOYMENT_ID: str = Field(min_length=1)
    SATELLITE_INTERNAL_URL: AnyHttpUrl
    COMPANION_TOKEN: str = Field(min_length=1)
    UPSTREAM_MODEL_URL: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8080")
    SERVING_PORT: int = Field(default=8000, ge=1, le=65535)
    INTERNAL_PORT: int = Field(default=8001, ge=1, le=65535)
    COMPANION_CACHE_TTL_SECONDS: float = Field(default=60.0, gt=0)
    COMPANION_CACHE_REFRESH_AHEAD_SECONDS: float = Field(default=15.0, ge=0)
    COMPANION_STALE_ALLOWANCE_SECONDS: float = Field(default=600.0, ge=0)
    COMPANION_NEGATIVE_CACHE_TTL_SECONDS: float = Field(default=10.0, gt=0)
    COMPANION_REQUEST_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    RETRY_BACKOFF_MAX_SECONDS: float = Field(default=30.0, gt=0)
    RECORDING_SAMPLE_RATE: float = Field(default=1.0, ge=0, le=1)
    RECORDING_BODY_MAX_BYTES: int = Field(default=65_536, gt=0)
    RECORDING_KEEP_INPUTS: bool = True
    RECORDING_KEEP_OUTPUTS: bool = True
    INJECTION_BODY_MAX_BYTES: int = Field(default=16_777_216, gt=0)
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_sidecar(self) -> Self:
        if self.SERVING_PORT == self.INTERNAL_PORT:
            raise ValueError("SERVING_PORT and INTERNAL_PORT must differ")
        if self.COMPANION_CACHE_REFRESH_AHEAD_SECONDS >= self.COMPANION_CACHE_TTL_SECONDS:
            raise ValueError(
                "COMPANION_CACHE_REFRESH_AHEAD_SECONDS must be less than "
                "COMPANION_CACHE_TTL_SECONDS"
            )
        return self

    def recording_policy(self) -> RecordingPolicy:
        return RecordingPolicy(
            sample_rate=self.RECORDING_SAMPLE_RATE,
            body_max_bytes=self.RECORDING_BODY_MAX_BYTES,
            keep_inputs=self.RECORDING_KEEP_INPUTS,
            keep_outputs=self.RECORDING_KEEP_OUTPUTS,
        )


class _SidecarRegistry:
    def __init__(
        self,
        deployment_id: str,
        upstream_url: str,
        default_policy: RecordingPolicy,
    ) -> None:
        self._deployment_id = deployment_id
        self._upstream_url = upstream_url
        self._default_policy = default_policy
        self._description = ModelDescription()
        self._deployment: LocalDeployment | None = None

    def set_description(self, description: ModelDescription) -> None:
        self._description = description

    def update(self, metadata: CompanionMetadata) -> None:
        if metadata.deployment_id != self._deployment_id:
            raise ValueError("companion metadata belongs to another deployment")
        secret_references = {attribute: attribute for attribute in metadata.secret_attributes}
        manifest = _mapping_copy(self._description.manifest)
        profile, profile_status = gate_reference_profile(
            manifest,
            _mapping_copy(self._description.reference_profile),
        )
        self._deployment = LocalDeployment(
            deployment_id=self._deployment_id,
            dynamic_attributes_secrets=secret_references,
            manifest=manifest,
            openapi_schema=without_secret_attributes(
                _mapping_copy(self._description.schema),
                secret_references,
            ),
            reference_profile=profile,
            profile_status=profile_status,
            monitoring_enabled=metadata.monitoring_enabled,
            metadata=metadata.metadata,
            upstream_url=self._upstream_url,
            recording_policy=(
                metadata.recording_policy.to_policy()
                if metadata.recording_policy is not None
                else self._default_policy
            ),
        )

    def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        if deployment_id != self._deployment_id:
            return None
        return self._deployment

    def list_deployments(self) -> tuple[LocalDeployment, ...]:
        return (self._deployment,) if self._deployment is not None else ()


class _Telemetry(Protocol):
    def shutdown(self) -> None: ...


class Sidecar:
    def __init__(
        self,
        configuration: SidecarConfiguration,
        *,
        companion: CompanionApi | None = None,
        upstream_client: httpx.AsyncClient | None = None,
        companion_transport: httpx.AsyncBaseTransport | None = None,
        upstream_transport: httpx.AsyncBaseTransport | None = None,
        recorder: Recorder | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self.configuration = configuration
        self._logger = logger or logging.getLogger("luml_satellite.serving.sidecar")
        self._sleep = sleep
        self._owns_upstream_client = upstream_client is None
        self._upstream = upstream_client or httpx.AsyncClient(
            transport=upstream_transport,
            timeout=45.0,
        )
        self._owns_companion = companion is None
        self.companion = companion or CompanionClient(
            str(configuration.SATELLITE_INTERNAL_URL),
            configuration.DEPLOYMENT_ID,
            configuration.COMPANION_TOKEN,
            transport=companion_transport,
            timeout_seconds=configuration.COMPANION_REQUEST_TIMEOUT_SECONDS,
        )
        cache_clock = clock or time.monotonic
        self.authorizer = CompanionAuthorizer(
            self.companion,
            ttl_seconds=configuration.COMPANION_CACHE_TTL_SECONDS,
            refresh_ahead_seconds=configuration.COMPANION_CACHE_REFRESH_AHEAD_SECONDS,
            stale_allowance_seconds=configuration.COMPANION_STALE_ALLOWANCE_SECONDS,
            negative_ttl_seconds=configuration.COMPANION_NEGATIVE_CACHE_TTL_SECONDS,
            clock=cache_clock,
            logger=self._logger,
        )
        self.secret_source = CompanionSecretSource(
            self.companion,
            configuration.DEPLOYMENT_ID,
            ttl_seconds=configuration.COMPANION_CACHE_TTL_SECONDS,
            refresh_ahead_seconds=configuration.COMPANION_CACHE_REFRESH_AHEAD_SECONDS,
            stale_allowance_seconds=configuration.COMPANION_STALE_ALLOWANCE_SECONDS,
            clock=cache_clock,
            logger=self._logger,
        )
        self._telemetry: _Telemetry | None = None
        if recorder is None:
            self.recorder, self._telemetry = _select_recorder(
                configuration.OTEL_EXPORTER_OTLP_ENDPOINT,
                self._logger,
            )
        else:
            self.recorder = recorder
        self._registry = _SidecarRegistry(
            configuration.DEPLOYMENT_ID,
            str(configuration.UPSTREAM_MODEL_URL),
            configuration.recording_policy(),
        )
        self._metadata_gate = StartingGate()
        self.application = create_serving_application(
            self._registry,
            self.authorizer,
            self.secret_source,
            recorder=self.recorder,
            upstream_client=self._upstream,
            starting_gate=self._metadata_gate,
            single_deployment_id=configuration.DEPLOYMENT_ID,
            injection_body_max_bytes=configuration.INJECTION_BODY_MAX_BYTES,
            authorization_unavailable_status_code=503,
            authorization_unavailable_detail="authorization unavailable",
            logger=self._logger,
        )
        self._description = ModelDescription()
        self.internal_application = create_sidecar_internal_application(
            configuration.COMPANION_TOKEN,
            description=lambda: self._description,
            health=self._upstream_is_healthy,
        )
        self._metadata_task: asyncio.Task[None] | None = None
        self._started = False

    @property
    def deployment(self) -> LocalDeployment | None:
        return self._registry.get_deployment(self.configuration.DEPLOYMENT_ID)

    async def start(self) -> None:
        if self._started:
            return
        await self._wait_for_upstream()
        self._description = await self._read_description()
        self._registry.set_description(self._description)
        self._metadata_task = asyncio.create_task(
            self._refresh_metadata(),
            name="luml-sidecar-metadata-refresh",
        )
        self._started = True

    async def aclose(self) -> None:
        if self._metadata_task is not None:
            self._metadata_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._metadata_task
        await self.authorizer.aclose()
        await self.secret_source.aclose()
        if self._owns_companion:
            close = getattr(self.companion, "aclose", None)
            if close is not None:
                await close()
        if self._owns_upstream_client:
            await self._upstream.aclose()
        if self._telemetry is not None:
            self._telemetry.shutdown()

    async def _wait_for_upstream(self) -> None:
        delay = 0.25
        while not await self._upstream_is_healthy():
            await self._sleep(delay)
            delay = min(self.configuration.RETRY_BACKOFF_MAX_SECONDS, delay * 2)

    async def _upstream_is_healthy(self) -> bool:
        try:
            response = await self._upstream.get(
                f"{str(self.configuration.UPSTREAM_MODEL_URL).rstrip('/')}/healthz"
            )
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def _read_description(self) -> ModelDescription:
        manifest, schema, reference_profile = await asyncio.gather(
            self._read_upstream_json("manifest"),
            self._read_upstream_json("openapi.json"),
            self._read_upstream_json("reference_profile"),
        )
        return ModelDescription(
            manifest=manifest,
            schema=schema,
            reference_profile=reference_profile,
        )

    async def _read_upstream_json(self, path: str) -> dict[str, Any] | None:
        try:
            response = await self._upstream.get(
                f"{str(self.configuration.UPSTREAM_MODEL_URL).rstrip('/')}/{path}"
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            self._logger.warning("could not read upstream %s: %s", path, error)
            return None
        return payload if isinstance(payload, dict) else None

    async def _refresh_metadata(self) -> None:
        retry_delay = 0.25
        while True:
            try:
                metadata = await self.companion.metadata()
                self._registry.update(metadata)
            except CompanionUnavailableError as error:
                if not _expected_boot_refusal(error):
                    self._logger.warning("could not refresh companion metadata: %s", error)
                await self._sleep(retry_delay)
                retry_delay = min(
                    self.configuration.RETRY_BACKOFF_MAX_SECONDS,
                    retry_delay * 2,
                )
                continue
            except Exception as error:
                self._logger.warning("could not refresh companion metadata: %s", error)
                await self._sleep(retry_delay)
                retry_delay = min(
                    self.configuration.RETRY_BACKOFF_MAX_SECONDS,
                    retry_delay * 2,
                )
                continue

            self.application.openapi_schema = None
            self._metadata_gate.mark_ready()
            retry_delay = 0.25
            await self._sleep(
                min(
                    self.configuration.COMPANION_CACHE_TTL_SECONDS,
                    metadata.ttl_seconds,
                )
            )


def create_sidecar_internal_application(
    companion_token: str,
    *,
    description: Callable[[], ModelDescription],
    health: Callable[[], Awaitable[bool]],
) -> FastAPI:
    application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    security = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> None:
        supplied = credentials.credentials if credentials is not None else ""
        if not hmac.compare_digest(supplied, companion_token):
            raise HTTPException(status_code=403, detail="Invalid companion token")

    dependencies = [Depends(verify_token)]

    @application.get("/healthz", dependencies=dependencies)
    async def healthz() -> dict[str, str]:
        if not await health():
            raise HTTPException(status_code=503, detail="Model server unavailable")
        return {"status": "healthy"}

    @application.get("/manifest", dependencies=dependencies)
    async def manifest() -> JSONResponse:
        return _description_response(description().manifest)

    @application.get("/openapi.json", dependencies=dependencies)
    async def openapi_schema() -> JSONResponse:
        return _description_response(description().schema)

    @application.get("/reference_profile", dependencies=dependencies)
    async def reference_profile() -> JSONResponse:
        return _description_response(description().reference_profile)

    return application


def _description_response(value: Mapping[str, Any] | None) -> JSONResponse:
    if value is None:
        raise HTTPException(status_code=404, detail="Description unavailable")
    return JSONResponse(cast(Any, value))


def _mapping_copy(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return copy.deepcopy(dict(value)) if value is not None else None


def _expected_boot_refusal(error: CompanionUnavailableError) -> bool:
    return getattr(error, "status_code", None) == 404


def _select_recorder(
    endpoint: str | None,
    logger: logging.Logger,
) -> tuple[Recorder, _Telemetry | None]:
    if not endpoint:
        logger.warning("sidecar monitoring is disabled because no telemetry endpoint is configured")
        return NoOpRecorder(), None
    try:
        from luml_satellite.monitoring import InferenceInstrumentation, create_telemetry
    except ImportError:
        logger.warning("sidecar monitoring is disabled because the monitoring extra is unavailable")
        return NoOpRecorder(), None
    telemetry = create_telemetry(endpoint=endpoint)
    return InferenceInstrumentation(telemetry), telemetry


async def run_sidecar(configuration: SidecarConfiguration) -> None:
    sidecar = Sidecar(configuration)
    await sidecar.start()
    serving = uvicorn.Server(
        uvicorn.Config(
            sidecar.application,
            host="0.0.0.0",
            port=configuration.SERVING_PORT,
            log_level=configuration.LOG_LEVEL.lower(),
        )
    )
    internal = uvicorn.Server(
        uvicorn.Config(
            sidecar.internal_application,
            host="0.0.0.0",
            port=configuration.INTERNAL_PORT,
            log_level=configuration.LOG_LEVEL.lower(),
        )
    )
    tasks = {
        asyncio.create_task(serving.serve(), name="luml-sidecar-serving"),
        asyncio.create_task(internal.serve(), name="luml-sidecar-internal"),
    }
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        serving.should_exit = True
        internal.should_exit = True
        await asyncio.gather(*pending)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await sidecar.aclose()


def main() -> None:
    configuration = SidecarConfiguration()  # type: ignore[call-arg]
    logging.basicConfig(level=configuration.LOG_LEVEL.upper())
    asyncio.run(run_sidecar(configuration))


if __name__ == "__main__":
    main()
