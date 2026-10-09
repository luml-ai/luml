import asyncio
import copy
import logging
from contextlib import suppress
from typing import Any, cast

import aiodocker
import httpx
import uvicorn
from fastapi import FastAPI
from luml_satellite import (
    ArtifactResolver,
    PlatformAuthorizer,
    PlatformClient,
    RecordingPolicy,
    SatelliteRuntime,
    TokenDeriver,
)
from luml_satellite.monitoring import MonitoringBundle
from luml_satellite.serving import InProcessServingPlacement, PlatformSecretSource
from uvicorn._types import ASGIApplication

from luml_satellite_docker.configuration import DockerConfiguration
from luml_satellite_docker.driver import DockerDriver

SLUG = "docker-2026.01-v2-debian12"
_LEGACY_COMPONENTS = (
    "DeploymentInfo",
    "Healthz",
    "InferenceAccessIn",
    "InferenceAccessOut",
    "MonitoringSessionInfo",
)
_DEPLOYMENT_INFO_DESCRIPTION = (
    "One row of the deployment listing — enough for a machine client to iterate.\n\n"
    'The monitoring fields are additive: the listing that always answered "what runs\n'
    'here" now also answers "what is monitored here", so a client with an API key can\n'
    "discover deployments without first consulting the Platform."
)


def pairing_document(application: FastAPI) -> dict[str, Any]:
    document = copy.deepcopy(application.openapi())
    schemas = document.get("components", {}).get("schemas", {})
    for name in _LEGACY_COMPONENTS:
        schema = schemas.get(name)
        if isinstance(schema, dict):
            schema.pop("additionalProperties", None)
    deployment_info = schemas.get("DeploymentInfo")
    if isinstance(deployment_info, dict):
        deployment_info["description"] = _DEPLOYMENT_INFO_DESCRIPTION
    validation_error = schemas.get("ValidationError")
    if isinstance(validation_error, dict):
        properties = validation_error.get("properties")
        if isinstance(properties, dict):
            properties.pop("ctx", None)
            properties.pop("input", None)
    return document


def build_runtime(
    configuration: DockerConfiguration,
    platform: PlatformClient,
    driver: DockerDriver,
    *,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
) -> SatelliteRuntime:
    tokens = TokenDeriver(configuration.SATELLITE_TOKEN, configuration.DERIVATION_KEY)
    artifacts = ArtifactResolver(
        platform,
        tokens,
        satellite_address=configuration.BASE_URL,
    )
    policy = RecordingPolicy(
        sample_rate=configuration.RECORDING_SAMPLE_RATE,
        body_max_bytes=configuration.RECORDING_BODY_MAX_BYTES,
        keep_inputs=configuration.RECORDING_KEEP_INPUTS,
        keep_outputs=configuration.RECORDING_KEEP_OUTPUTS,
    )
    placements: list[InProcessServingPlacement] = []
    monitoring = (
        MonitoringBundle(
            configuration,
            platform,
            deployments=lambda: placements[0].deployments if placements else (),
        )
        if configuration.MONITORING_ENABLED
        else None
    )
    placement = InProcessServingPlacement(
        PlatformAuthorizer(platform),
        PlatformSecretSource(platform),
        recorder=monitoring.recorder if monitoring is not None else None,
        recording_policy=policy,
        artifact_resolver=artifacts,
        injection_body_max_bytes=configuration.INJECTION_BODY_MAX_BYTES,
        upstream_transport=upstream_transport,
        last_monitored_at=(
            (
                lambda deployment_id: (
                    monitoring.worker_health.snapshot(deployment_id).deployment.last_window_end
                )
            )
            if monitoring is not None
            else None
        ),
    )
    placements.append(placement)
    placement.include_internal_routes()
    if monitoring is not None:
        monitoring.mount(placement.application)

    return SatelliteRuntime(
        configuration,
        platform,
        driver,
        serving=placement,
        monitoring=monitoring,
        artifact_resolver=artifacts,
        public_application=placement.application,
        internal_application=placement.application,
        pairing_document=lambda: pairing_document(placement.application),
        slug=SLUG,
        on_paired=lambda paired: driver.bind_satellite(paired.id),
    )


async def run_async(
    configuration: DockerConfiguration | None = None,
    *,
    docker_client: aiodocker.Docker | None = None,
    platform_transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    active_configuration = configuration or DockerConfiguration()  # type: ignore[call-arg]
    logging.basicConfig(level=active_configuration.LOG_LEVEL.upper())
    async with (
        PlatformClient(
            str(active_configuration.PLATFORM_URL),
            active_configuration.SATELLITE_TOKEN,
            transport=platform_transport,
        ) as platform,
        DockerDriver(active_configuration, client=docker_client) as driver,
    ):
        runtime = build_runtime(active_configuration, platform, driver)
        application = runtime.public_application
        if application is None:
            raise RuntimeError("Docker satellite has no public application")
        server = uvicorn.Server(
            uvicorn.Config(
                cast(ASGIApplication, application),
                host="0.0.0.0",
                port=active_configuration.AGENT_PORT,
                log_level=active_configuration.LOG_LEVEL.lower(),
            )
        )
        server_task = asyncio.create_task(server.serve(), name="luml-docker-http")
        runtime_task: asyncio.Task[None] | None = None
        try:
            await _wait_until_started(server, server_task)
            runtime_task = asyncio.create_task(
                runtime.run_forever(),
                name="luml-docker-runtime",
            )
            done, _ = await asyncio.wait(
                {server_task, runtime_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if server_task in done:
                runtime.stop()
                runtime_task.cancel()
                with suppress(asyncio.CancelledError):
                    await runtime_task
                await server_task
            else:
                server.should_exit = True
                await server_task
                await runtime_task
        finally:
            runtime.stop()
            server.should_exit = True
            if runtime_task is not None and not runtime_task.done():
                runtime_task.cancel()
                with suppress(asyncio.CancelledError):
                    await runtime_task
            if not server_task.done():
                with suppress(Exception):
                    await asyncio.wait_for(server_task, timeout=2.0)


async def _wait_until_started(
    server: uvicorn.Server,
    server_task: asyncio.Task[None],
) -> None:
    while not server.started:
        if server_task.done():
            await server_task
            raise RuntimeError("HTTP server exited before startup")
        await asyncio.sleep(0.01)


def main() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
