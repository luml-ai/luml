import asyncio
from contextlib import suppress

import uvicorn

from agent.agent_api import create_agent_app
from agent.agent_manager import SatelliteManager
from agent.clients import DockerService, PlatformClient
from agent.controllers import PeriodicController
from agent.handlers.handler_instances import ms_handler
from agent.handlers.tasks import TaskHandler
from agent.monitoring import (
    GreptimeMonitoringStore,
    MonitoringWorker,
    default_registry,
    monitored_deployments,
)
from agent.settings import config


def _build_monitoring_worker() -> tuple[MonitoringWorker, GreptimeMonitoringStore]:
    store = GreptimeMonitoringStore(
        host=config.GREPTIMEDB_HOST,
        port=config.GREPTIMEDB_HTTP_PORT,
        database=config.GREPTIMEDB_DATABASE,
    )
    worker = MonitoringWorker(
        store=store,
        registry=default_registry(
            latency_p95_threshold_ms=config.MONITORING_LATENCY_P95_THRESHOLD_MS
        ),
        provider=lambda: monitored_deployments(ms_handler.deployments.values()),
        window_seconds=config.MONITORING_WINDOW_SEC,
        interval_seconds=config.MONITORING_INTERVAL_SEC,
    )
    return worker, store


async def run_async() -> None:
    async with PlatformClient(str(config.PLATFORM_URL), config.SATELLITE_TOKEN) as platform:
        agent_app = create_agent_app(platform.authorize_inference_access)

        uv_config = uvicorn.Config(
            agent_app,
            host="0.0.0.0",
            log_level="warning",
        )
        uv_server = uvicorn.Server(uv_config)
        uv_task = asyncio.create_task(uv_server.serve())
        async with DockerService() as docker:
            handler = TaskHandler(platform=platform, docker=docker)
            controller = PeriodicController(
                handler=handler, poll_interval_s=float(config.POLL_INTERVAL_SEC)
            )
            satellite_manager = SatelliteManager(platform)

            monitoring_worker = None
            monitoring_store = None
            monitoring_task = None
            if config.MONITORING_ENABLED:
                monitoring_worker, monitoring_store = _build_monitoring_worker()
                monitoring_task = asyncio.create_task(monitoring_worker.run_forever())

            try:
                await asyncio.sleep(0.1)

                await satellite_manager.pair()

                await controller.run_forever()
            finally:
                if monitoring_worker is not None:
                    monitoring_worker.stop()
                if monitoring_task is not None:
                    monitoring_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await monitoring_task
                if monitoring_store is not None:
                    with suppress(Exception):
                        await monitoring_store.aclose()
                uv_server.should_exit = True
                with suppress(Exception):
                    await asyncio.wait_for(uv_task, timeout=2.0)


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
