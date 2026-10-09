import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from luml_satellite.authorization import Authorizer
from luml_satellite.declaration import SatelliteConfiguration
from luml_satellite.monitoring.bundle import MonitoringBundle, MonitoringRole
from luml_satellite.monitoring.deployments import DeploymentSource, PlatformDeploymentSource
from luml_satellite.monitoring.storage.query_store import MonitoringStore as QueryStore
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import PlatformClient


def create_dashboard_application(
    configuration: SatelliteConfiguration,
    *,
    platform: PlatformClient | None = None,
    deployment_source: DeploymentSource | None = None,
    query_store: QueryStore | None = None,
    authorizer: Authorizer | None = None,
) -> FastAPI:
    owns_platform = platform is None
    platform_client = platform or PlatformClient(
        str(configuration.PLATFORM_URL), configuration.SATELLITE_TOKEN
    )
    source = deployment_source or PlatformDeploymentSource(
        platform_client,
        configuration.SIDECAR_INTERNAL_URL_TEMPLATE,
        TokenDeriver(configuration.SATELLITE_TOKEN, configuration.DERIVATION_KEY),
        refresh_seconds=configuration.MONITORING_DEPLOYMENTS_REFRESH_SEC,
    )
    bundle = MonitoringBundle(
        configuration,
        platform_client,
        role=MonitoringRole.DASHBOARD,
        deployment_source=source,
        query_store=query_store,
        authorizer=authorizer,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            if owns_platform:
                async with platform_client:
                    yield
            else:
                yield
        finally:
            await bundle.aclose()

    application = FastAPI(lifespan=lifespan)
    application.state.monitoring_bundle = bundle
    bundle.mount(application)
    return application


def main() -> None:
    configuration = SatelliteConfiguration()  # type: ignore[call-arg]
    logging.basicConfig(level=configuration.LOG_LEVEL.upper())
    application = create_dashboard_application(configuration)
    uvicorn.run(
        application,
        host="0.0.0.0",
        port=configuration.AGENT_PORT,
        log_level=configuration.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
