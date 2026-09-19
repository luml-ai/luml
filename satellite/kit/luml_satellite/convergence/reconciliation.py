import logging
import random
from collections.abc import Callable
from typing import Any, Protocol

from luml_satellite.workload import Clock, SystemClock

from .manager import Convergence
from .polling import PollingPass


class ReconciliationPlatform(Protocol):
    async def list_deployments(self) -> list[dict[str, Any]]: ...


class Reconciliation:
    def __init__(
        self,
        platform: ReconciliationPlatform,
        convergence: Convergence,
        polling: PollingPass,
        *,
        clock: Clock | None = None,
        backoff_base: float = 1.0,
        backoff_cap: float = 60.0,
        jitter: Callable[[float], float] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if backoff_base <= 0:
            raise ValueError("backoff_base must be greater than zero")
        if backoff_cap <= 0:
            raise ValueError("backoff_cap must be greater than zero")
        self.platform = platform
        self.convergence = convergence
        self.polling = polling
        self.clock = clock or SystemClock()
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.jitter = jitter or _full_jitter
        self.logger = logger or logging.getLogger("luml_satellite.reconciliation")

    async def run(self) -> None:
        deployments = await self._list_deployments()
        await self.convergence.reconcile_deployments(deployments)
        await self.polling.resume_running()
        await self.convergence.cleanup_orphans(deployments)

    async def _list_deployments(self) -> list[dict[str, Any]]:
        failures = 0
        while True:
            try:
                return await self.platform.list_deployments()
            except Exception as error:
                failures += 1
                exponent = min(failures - 1, 62)
                ceiling = min(
                    self.backoff_cap,
                    self.backoff_base * (2**exponent),
                )
                delay = max(0.0, min(ceiling, self.jitter(ceiling)))
                self.logger.warning(
                    "could not list deployments during reconciliation; retrying in %.3fs: %s",
                    delay,
                    error,
                )
                await self.clock.sleep(delay)


def _full_jitter(ceiling: float) -> float:
    return random.uniform(0.0, ceiling)
