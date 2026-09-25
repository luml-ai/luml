import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from functools import partial
from typing import Any, Protocol

from pydantic import ValidationError

from luml_satellite.wire import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from .manager import Convergence

type CustomTaskHandler = Callable[[SatelliteQueueTask], Awaitable[None]]

_BUILT_IN_TYPES = frozenset(task_type.value for task_type in SatelliteTaskType)


class PollingPlatform(Protocol):
    async def list_tasks(
        self,
        status: SatelliteTaskStatus | str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def update_task_status(
        self,
        task_id: str,
        status: SatelliteTaskStatus | str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class PollingPass:
    def __init__(
        self,
        platform: PollingPlatform,
        convergence: Convergence,
        *,
        custom_handlers: Mapping[str, CustomTaskHandler] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.platform = platform
        self.convergence = convergence
        self.custom_handlers = dict(custom_handlers or {})
        self.logger = logger or logging.getLogger("luml_satellite.polling")
        self._in_flight: dict[str, asyncio.Task[None]] = {}

    @property
    def in_flight(self) -> frozenset[str]:
        return frozenset(self._in_flight)

    async def run(self) -> None:
        existing_entries = set(self.convergence.in_progress)
        raw_tasks = await self.platform.list_tasks(SatelliteTaskStatus.PENDING)
        ready_tasks: list[tuple[SatelliteQueueTask, CustomTaskHandler | None]] = []
        seen_task_ids = set(self._in_flight)
        for raw_task in raw_tasks:
            task = await self._parse(raw_task)
            if task is None:
                continue

            handler = self.custom_handlers.get(task.type)
            if task.type not in _BUILT_IN_TYPES and handler is None:
                await self._fail_raw_task(task.id, f"unknown type: {task.type}")
                continue
            if task.type in _BUILT_IN_TYPES and _deployment_id(task) is None:
                await self._fail_raw_task(task.id, "invalid task payload")
                continue
            if task.id in seen_task_ids:
                continue
            seen_task_ids.add(task.id)
            ready_tasks.append((task, handler))

        for task, handler in ready_tasks:
            scheduled = asyncio.create_task(
                self._run_task(task, handler),
                name=f"satellite-task-{task.id}",
            )
            self._in_flight[task.id] = scheduled
            scheduled.add_done_callback(partial(self._task_finished, task.id))

        await asyncio.sleep(0)
        await self.convergence.revisit_in_progress(
            skip_locked=True,
            deployment_ids=existing_entries,
        )

    async def poll(self) -> None:
        await self.run()

    async def resume_running(self) -> None:
        raw_tasks = await self.platform.list_tasks(SatelliteTaskStatus.RUNNING)
        resumable: list[tuple[SatelliteQueueTask, CustomTaskHandler | None]] = []
        for raw_task in raw_tasks:
            task = await self._parse(raw_task)
            if task is None:
                continue
            handler = self.custom_handlers.get(task.type)
            if task.type not in _BUILT_IN_TYPES and handler is None:
                await self._fail_raw_task(task.id, f"unknown type: {task.type}")
                continue
            if task.type in _BUILT_IN_TYPES and _deployment_id(task) is None:
                await self._fail_raw_task(task.id, "invalid task payload")
                continue
            resumable.append((task, handler))

        await asyncio.gather(*(self._resume_task(task, handler) for task, handler in resumable))

    async def drain(self) -> None:
        while self._in_flight:
            tasks = tuple(self._in_flight.values())
            await asyncio.gather(*tasks, return_exceptions=True)
            for task_id, task in tuple(self._in_flight.items()):
                if task.done():
                    self._in_flight.pop(task_id, None)

    async def _parse(self, raw_task: dict[str, Any]) -> SatelliteQueueTask | None:
        try:
            return SatelliteQueueTask.model_validate(raw_task)
        except ValidationError as error:
            self.logger.error("task payload is invalid: %s", error)
            task_id = raw_task.get("id")
            if isinstance(task_id, str):
                await self._fail_raw_task(task_id, "invalid task payload")
            return None

    async def _run_task(
        self,
        task: SatelliteQueueTask,
        custom_handler: CustomTaskHandler | None,
    ) -> None:
        if custom_handler is not None and task.type not in _BUILT_IN_TYPES:
            try:
                await self.convergence.run_custom(task, custom_handler)
            except Exception as error:
                self.logger.error("custom task '%s' failed: %s", task.id, error)
                await self._fail_raw_task(task.id, f"handler error: {error}")
            return

        try:
            await self.convergence.handle_task(task)
        except Exception as error:
            self.logger.exception("task '%s' handler failed", task.id)
            await self._fail_raw_task(task.id, f"handler error: {error}")

    async def _resume_task(
        self,
        task: SatelliteQueueTask,
        custom_handler: CustomTaskHandler | None,
    ) -> None:
        if custom_handler is not None and task.type not in _BUILT_IN_TYPES:
            try:
                await self.convergence.run_custom(task, custom_handler)
            except Exception as error:
                self.logger.error("resumed custom task '%s' failed: %s", task.id, error)
                await self._fail_raw_task(task.id, f"handler error: {error}")
            return
        try:
            await self.convergence.resume_task(task)
        except Exception as error:
            self.logger.exception("resumed task '%s' handler failed", task.id)
            await self._fail_raw_task(task.id, f"handler error: {error}")

    async def _fail_raw_task(self, task_id: str, reason: str) -> None:
        try:
            await self.platform.update_task_status(
                task_id,
                SatelliteTaskStatus.FAILED,
                {"reason": reason},
            )
        except Exception as error:
            self.logger.error("could not fail task '%s': %s", task_id, error)

    def _task_finished(self, task_id: str, completed: asyncio.Task[None]) -> None:
        self._in_flight.pop(task_id, None)
        if completed.cancelled():
            return
        error = completed.exception()
        if error is not None:
            self.logger.error("task '%s' ended unexpectedly: %s", task_id, error)


TaskPoller = PollingPass


def _deployment_id(task: SatelliteQueueTask) -> str | None:
    value = (task.payload or {}).get("deployment_id")
    return value if isinstance(value, str) and value else None
