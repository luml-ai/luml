"""Main entry point for the deploy satellite."""

import asyncio
from contextlib import suppress
from typing import Any

import uvicorn  # type: ignore[import-not-found]
from luml_satellite_sdk import (
    PeriodicController,
    PlatformClient,
    SatelliteManager,
    SatelliteQueueTask,
    SatelliteTaskType,
    TaskHandler,
    TaskProtocol,
    TaskRegistry,
)

from deploy_satellite.api import create_agent_app
from deploy_satellite.docker import DockerService
from deploy_satellite.model_server.handler import ModelServerHandler
from deploy_satellite.settings import settings
from deploy_satellite.tasks import DeployTask, UndeployTask


class DeployTaskAdapter(TaskProtocol):
    """Adapter to bridge DeployTask (BaseTask) to TaskProtocol interface."""

    def __init__(self, task: DeployTask) -> None:
        self._task = task

    async def run(self, task: SatelliteQueueTask) -> None:
        """Execute the deploy task."""
        await self._task.execute(task.model_dump())


class UndeployTaskAdapter(TaskProtocol):
    """Adapter to bridge UndeployTask (BaseTask) to TaskProtocol interface."""

    def __init__(self, task: UndeployTask) -> None:
        self._task = task

    async def run(self, task: SatelliteQueueTask) -> None:
        """Execute the undeploy task."""
        await self._task.execute(task.model_dump())


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
    """Run the deploy satellite asynchronously."""
    async with PlatformClient(str(settings.api_url), settings.api_key) as platform:
        ms_handler = ModelServerHandler()

        agent_app = create_agent_app(
            ms_handler=ms_handler,
            authorize_access=platform.authorize_inference_access,
            platform_url=str(settings.api_url),
            satellite_token=settings.api_key,
        )

        uv_config = uvicorn.Config(
            agent_app,
            host=settings.agent_api_host,
            port=settings.agent_api_port,
            log_level="warning",
        )
        uv_server = uvicorn.Server(uv_config)
        uv_task = asyncio.create_task(uv_server.serve())

        async with DockerService(
            network_name=settings.docker_network,
            model_server_port=settings.model_server_port,
        ) as docker:
            # Build task registry with satellite-specific task handlers
            deploy_task = DeployTask(
                platform=platform,
                docker=docker,
                model_image=settings.model_image,
                model_server_port=settings.model_server_port,
            )
            undeploy_task = UndeployTask(
                platform=platform,
                docker=docker,
            )

            task_registry: TaskRegistry = {
                SatelliteTaskType.DEPLOY: DeployTaskAdapter(deploy_task),
                SatelliteTaskType.UNDEPLOY: UndeployTaskAdapter(undeploy_task),
            }

            handler = TaskHandler(platform=platform, task_registry=task_registry)
            controller = PeriodicController(
                platform=platform,
                dispatch=handler.dispatch,
                poll_interval_s=settings.polling_interval,
            )

            satellite_manager = SatelliteManager(platform)
            satellite_manager.register_capabilities(get_capabilities())

            try:
                await asyncio.sleep(0.1)

                await satellite_manager.pair(
                    base_url=settings.base_url.rstrip("/"),
                    slug="docker-2026.01-v1-debian12",
                )

                await controller.run_forever()
            finally:
                uv_server.should_exit = True
                with suppress(Exception):
                    await asyncio.wait_for(uv_task, timeout=2.0)


def run() -> None:
    """Run the deploy satellite."""
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
