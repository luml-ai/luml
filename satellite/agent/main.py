import asyncio
from contextlib import suppress
from typing import Any

import uvicorn

from agent.agent_api import create_deploy_router, setup_custom_openapi
from agent.clients import DockerService
from agent.handlers.handler_instances import ms_handler
from agent.settings import config
from agent.tasks import DeployTask, UndeployTask
from luml_satellite_kit import (
    PeriodicController,
    PlatformClient,
    SatelliteManager,
    SatelliteTaskType,
    TaskDispatcher,
    create_satellite_app,
)

SATELLITE_SLUG = "docker-2026.01-v1-debian12"


def get_capabilities() -> dict[str, Any]:
    return {
        "deploy": {
            "version": 1,
            "supported_variants": ["pyfunc", "pipeline"],
            "supported_tags_combinations": None,
            "extra_fields_form_spec": None,
        }
    }


async def run_async() -> None:
    async with PlatformClient(str(config.PLATFORM_URL), config.SATELLITE_TOKEN) as platform:
        deploy_router = create_deploy_router(platform.authorize_inference_access)
        agent_app = create_satellite_app(extra_routers=[deploy_router])
        setup_custom_openapi(agent_app)

        uv_config = uvicorn.Config(
            agent_app,
            host="0.0.0.0",
            log_level="warning",
        )
        uv_server = uvicorn.Server(uv_config)
        uv_task = asyncio.create_task(uv_server.serve())

        asyncio.create_task(ms_handler.sync_deployments())

        async with DockerService() as docker:
            deploy = DeployTask(platform=platform, docker=docker)
            undeploy = UndeployTask(platform=platform, docker=docker)

            dispatcher = TaskDispatcher(
                handlers={
                    SatelliteTaskType.DEPLOY: deploy,
                    SatelliteTaskType.UNDEPLOY: undeploy,
                },
                platform=platform,
            )
            controller = PeriodicController(
                handler=dispatcher, poll_interval_s=float(config.POLL_INTERVAL_SEC)
            )
            satellite_manager = SatelliteManager(
                platform,
                capabilities=get_capabilities(),
                slug=SATELLITE_SLUG,
                base_url=config.BASE_URL,
            )
            try:
                await asyncio.sleep(0.1)

                await satellite_manager.pair()

                await controller.run_forever()
            finally:
                uv_server.should_exit = True
                with suppress(Exception):
                    await asyncio.wait_for(uv_task, timeout=2.0)


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
