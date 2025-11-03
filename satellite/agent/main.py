import asyncio
from contextlib import suppress

import uvicorn

from agent.handlers.tasks import TaskHandler

from .agent_api import create_agent_app
from .agent_manager import SatelliteManager
from .clients import DockerService, PlatformClient
from .controllers import PeriodicController
from .settings import config


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
