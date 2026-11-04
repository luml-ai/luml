from __future__ import annotations

import asyncio
from typing import Any

from textual.pilot import Pilot


async def settle_workers(pilot: Pilot[Any], *, max_rounds: int = 20) -> None:
    """Wait for all app workers and the callbacks they post back.

    `pilot.pause()` only drains the event loop; it does not wait for
    `@work(thread=True)` workers. A thread worker's `call_from_thread`
    callback runs before the worker finishes, so once the workers are done
    a pause processes whatever the callback queued. Callbacks may start
    further workers (e.g. a reload), hence the loop.
    """

    app = pilot.app
    for _ in range(max_rounds):
        workers = list(app.workers)
        if all(worker.is_finished for worker in workers):
            await pilot.pause()
            return
        # Cancelled exclusive workers raise from `wait()`; they still count
        # as settled.
        await asyncio.gather(
            *(worker.wait() for worker in workers), return_exceptions=True
        )
        await pilot.pause()
    raise AssertionError("app workers did not settle")
