import argparse
import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

from luml_satellite.declaration import SatelliteConfiguration
from luml_satellite.monitoring.bundle import MonitoringBundle, MonitoringRole
from luml_satellite.monitoring.compute.heartbeat import heartbeat_file_is_fresh
from luml_satellite.monitoring.deployments import PlatformDeploymentSource
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import PlatformClient


def probe_exit_code(configuration: SatelliteConfiguration) -> int:
    fresh = heartbeat_file_is_fresh(
        Path(configuration.MONITORING_HEARTBEAT_FILE),
        interval_seconds=configuration.MONITORING_INTERVAL_SEC,
    )
    return 0 if fresh else 1


async def run_worker(configuration: SatelliteConfiguration) -> None:
    platform = PlatformClient(str(configuration.PLATFORM_URL), configuration.SATELLITE_TOKEN)
    tokens = TokenDeriver(configuration.SATELLITE_TOKEN, configuration.DERIVATION_KEY)
    source = PlatformDeploymentSource(
        platform,
        configuration.SIDECAR_INTERNAL_URL_TEMPLATE,
        tokens,
        refresh_seconds=configuration.MONITORING_DEPLOYMENTS_REFRESH_SEC,
    )
    bundle = MonitoringBundle(
        configuration,
        platform,
        role=MonitoringRole.WORKER,
        deployment_source=source,
        heartbeat_file=configuration.MONITORING_HEARTBEAT_FILE,
    )
    try:
        async with platform:
            await bundle.worker.run_forever()
    finally:
        await bundle.aclose()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="luml-monitoring-worker")
    parser.add_argument("--probe", action="store_true")
    arguments = parser.parse_args(argv)
    configuration = SatelliteConfiguration()  # type: ignore[call-arg]
    logging.basicConfig(level=configuration.LOG_LEVEL.upper())
    if arguments.probe:
        raise SystemExit(probe_exit_code(configuration))
    asyncio.run(run_worker(configuration))


if __name__ == "__main__":
    main()
