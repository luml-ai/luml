"""Periodic polling controller for LUML Satellite implementations."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from luml_satellite_sdk.client import BasePlatformClient
from luml_satellite_sdk.schemas import SatelliteTaskStatus

logger = logging.getLogger("satellite")


class PeriodicController:
    """Controller that periodically polls for tasks and dispatches them.

    This controller implements the standard polling loop pattern for satellites:
    1. Poll the platform for pending tasks at a configurable interval
    2. Dispatch each task to a handler callback
    3. Handle errors by updating task status to failed

    Usage:
        async def dispatch_task(task: dict[str, Any]) -> None:
            # Handle the task
            ...

        controller = PeriodicController(
            platform=platform_client,
            dispatch=dispatch_task,
            poll_interval_s=5.0,
        )
        await controller.run_forever()
    """

    def __init__(
        self,
        *,
        platform: BasePlatformClient,
        dispatch: Callable[[dict[str, Any]], Awaitable[None]],
        poll_interval_s: float,
    ) -> None:
        """Initialize the periodic controller.

        Args:
            platform: The platform client for API communication.
            dispatch: Async callback function to handle each task.
            poll_interval_s: Interval between polling cycles in seconds.
        """
        self.platform = platform
        self.dispatch = dispatch
        self.poll_interval_s = poll_interval_s
        self._stopped = False

    def stop(self) -> None:
        """Signal the controller to stop after the current cycle."""
        self._stopped = True

    async def tick(self) -> None:
        """Execute one polling cycle.

        Fetches pending tasks from the platform and dispatches each one.
        If a task dispatch fails, updates the task status to failed.
        """
        tasks = await self.platform.list_tasks(SatelliteTaskStatus.PENDING)
        if len(tasks) > 0:
            logger.info(
                f"[tasks] Found {len(tasks)} pending tasks: "
                f"{[t.get('id', 'unknown') for t in tasks]}"
            )
        for task in tasks:
            try:
                await self.dispatch(task)
            except Exception as error:
                with suppress(Exception):
                    await self.platform.update_task_status(
                        task["id"],
                        SatelliteTaskStatus.FAILED,
                        {"reason": f"handler error: {error}"},
                    )

    async def run_forever(self) -> None:
        """Run the polling loop until stopped.

        Continuously polls for tasks at the configured interval.
        Handles KeyboardInterrupt for graceful shutdown.
        """
        logger.info("[satellite] starting periodic controller...")
        while not self._stopped:
            try:
                await self.tick()
            except KeyboardInterrupt:
                self._stopped = True
                break
            except Exception as e:
                logger.info(f"[satellite] tick error: {e}")
            await asyncio.sleep(self.poll_interval_s)
