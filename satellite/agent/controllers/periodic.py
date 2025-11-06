import asyncio
import logging
from contextlib import suppress

from agent.handlers import TaskHandler
from agent.schemas import SatelliteTaskStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger("satellite")


class PeriodicController:
    def __init__(self, *, handler: TaskHandler, poll_interval_s: float) -> None:
        self.handler = handler
        self.poll_interval_s = poll_interval_s
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    async def tick(self) -> None:
        tasks = await self.handler.platform.list_tasks(SatelliteTaskStatus.PENDING)
        if len(tasks) > 0:
            logger.info(
                f"[tasks] Found {len(tasks)} pending tasks: "
                f"{[t.get('id', 'unknown') for t in tasks]}"
            )
        for task in tasks:
            try:
                await self.handler.dispatch(task)
            except Exception as error:
                with suppress(Exception):
                    await self.handler.platform.update_task_status(
                        task["id"],
                        SatelliteTaskStatus.FAILED,
                        {"reason": f"handler error: {error}"},
                    )

    async def run_forever(self) -> None:
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
