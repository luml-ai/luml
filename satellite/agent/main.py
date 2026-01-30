import asyncio
from contextlib import suppress
from typing import Any

import uvicorn
from luml_satellite_sdk import (
    PeriodicController,
    PlatformClient,
    SatelliteManager,
    SatelliteTaskType,
    TaskHandler,
)

from agent.agent_api import create_agent_app
from agent.clients import DockerService
from agent.settings import config
from agent.tasks import DeployTask, UndeployTask


def get_capabilities() -> list[dict[str, Any]]:
    """Return the capabilities supported by this satellite."""
    return [
        {
            "deploy": {
                "version": 1,
                "supported_variants": ["pyfunc", "pipeline"],
                "supported_tags_combinations": None,
                "extra_fields_form_spec": None,
            }
        }
    ]


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
            # Build task registry with satellite-specific task handlers
            task_registry = {
                SatelliteTaskType.DEPLOY: DeployTask(platform=platform, docker=docker),
                SatelliteTaskType.UNDEPLOY: UndeployTask(platform=platform, docker=docker),
            }
            handler = TaskHandler(platform=platform, task_registry=task_registry)
            controller = PeriodicController(
                platform=platform,
                dispatch=handler.dispatch,
                poll_interval_s=float(config.POLL_INTERVAL_SEC),
            )
            satellite_manager = SatelliteManager(platform)
            satellite_manager.register_capabilities(get_capabilities())
            try:
                await asyncio.sleep(0.1)

                await satellite_manager.pair(
                    base_url=config.BASE_URL.rstrip("/"),
                    slug="docker-2026.01-v1-debian12",
                )

                await controller.run_forever()
            finally:
                uv_server.should_exit = True
                with suppress(Exception):
                    await asyncio.wait_for(uv_task, timeout=2.0)


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
