import asyncio
import logging
from contextlib import suppress
from typing import Any, cast

import uvicorn
from kubernetes_asyncio import config as kubernetes_config
from luml_satellite import (
    ArtifactResolver,
    PlatformAuthorizer,
    PlatformClient,
    RecordingPolicy,
    SatelliteRuntime,
)
from luml_satellite.monitoring import MonitoringBundle, MonitoringRole
from luml_satellite.serving import CompanionServingPlacement, PlatformSecretSource
from uvicorn._types import ASGIApplication

from luml_satellite_kubernetes.api import KubernetesApi, KubernetesApiClient
from luml_satellite_kubernetes.configuration import KubernetesConfiguration
from luml_satellite_kubernetes.driver import KubernetesDriver

SLUG = "kubernetes-2026.01-v1"


def build_runtime(
    configuration: KubernetesConfiguration,
    platform: PlatformClient,
    driver: KubernetesDriver,
    *,
    upstream_transport: object | None = None,
) -> SatelliteRuntime:
    tokens = driver.tokens
    artifacts = ArtifactResolver(
        platform,
        tokens,
        satellite_address=configuration.SATELLITE_INTERNAL_URL,
    )
    policy = RecordingPolicy(
        sample_rate=configuration.RECORDING_SAMPLE_RATE,
        body_max_bytes=configuration.RECORDING_BODY_MAX_BYTES,
        keep_inputs=configuration.RECORDING_KEEP_INPUTS,
        keep_outputs=configuration.RECORDING_KEEP_OUTPUTS,
    )
    monitoring = (
        MonitoringBundle(
            configuration,
            platform,
            role=MonitoringRole.SATELLITE,
        )
        if configuration.MONITORING_ENABLED
        else None
    )
    placement = CompanionServingPlacement(
        PlatformAuthorizer(platform),
        PlatformSecretSource(platform),
        tokens,
        recording_policy=policy,
        artifact_resolver=artifacts,
        upstream_transport=cast(Any, upstream_transport),
    )
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
        internal_application=placement.internal_application,
        pairing_document=placement.application.openapi,
        slug=configuration.SATELLITE_SLUG,
        on_paired=lambda paired: driver.bind_satellite(paired.id),
    )


async def run_async(
    configuration: KubernetesConfiguration | None = None,
    *,
    api: KubernetesApiClient | None = None,
) -> None:
    active_configuration = configuration or KubernetesConfiguration()  # type: ignore[call-arg]
    logging.basicConfig(level=active_configuration.LOG_LEVEL.upper())
    active_api = api
    if active_api is None:
        kubernetes_config.load_incluster_config()  # type: ignore[no-untyped-call]
        active_api = KubernetesApi(
            active_configuration.NAMESPACE,
            field_manager=active_configuration.KUBERNETES_FIELD_MANAGER,
        )

    async with PlatformClient(
        str(active_configuration.PLATFORM_URL),
        active_configuration.SATELLITE_TOKEN,
    ) as platform:
        driver = KubernetesDriver(active_configuration, active_api)
        runtime = build_runtime(active_configuration, platform, driver)
        public_application = runtime.public_application
        internal_application = runtime.internal_application
        if public_application is None or internal_application is None:
            raise RuntimeError("Kubernetes satellite requires public and internal applications")
        public_server = _server(
            public_application,
            active_configuration.AGENT_PORT,
            active_configuration.LOG_LEVEL,
        )
        internal_server = _server(
            internal_application,
            active_configuration.INTERNAL_PORT,
            active_configuration.LOG_LEVEL,
        )
        public_task = asyncio.create_task(public_server.serve(), name="luml-kubernetes-public")
        internal_task = asyncio.create_task(
            internal_server.serve(),
            name="luml-kubernetes-internal",
        )
        runtime_task: asyncio.Task[None] | None = None
        try:
            await asyncio.gather(
                _wait_until_started(public_server, public_task),
                _wait_until_started(internal_server, internal_task),
            )
            runtime_task = asyncio.create_task(
                runtime.run_forever(),
                name="luml-kubernetes-runtime",
            )
            done, _ = await asyncio.wait(
                {public_task, internal_task, runtime_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if runtime_task not in done:
                runtime.stop()
                runtime_task.cancel()
                with suppress(asyncio.CancelledError):
                    await runtime_task
            else:
                await runtime_task
        finally:
            runtime.stop()
            public_server.should_exit = True
            internal_server.should_exit = True
            if runtime_task is not None and not runtime_task.done():
                runtime_task.cancel()
                with suppress(asyncio.CancelledError):
                    await runtime_task
            for task in (public_task, internal_task):
                if not task.done():
                    with suppress(Exception):
                        await asyncio.wait_for(task, timeout=2.0)
            await driver.aclose()


def _server(application: object, port: int, log_level: str) -> uvicorn.Server:
    return uvicorn.Server(
        uvicorn.Config(
            cast(ASGIApplication, application),
            host="0.0.0.0",
            port=port,
            log_level=log_level.lower(),
        )
    )


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
