import asyncio
import logging
import signal
import sys
from types import FrameType

from handlers.model_handler import ModelHandler

logger = logging.getLogger(__name__)


async def main() -> None:
    model_handler: ModelHandler | None = None

    def terminate(signum: int, frame: FrameType | None) -> None:
        raise SystemExit(0)

    previous_handler = signal.signal(signal.SIGTERM, terminate)
    try:
        try:
            model_handler = ModelHandler()
        except Exception as error:
            logger.error(f"[main] Failed to initialize ModelHandler: {error}")
            sys.exit(1)

        if model_handler.conda_worker is None:
            logger.error("[main] No conda worker found")
            return
        process = model_handler.conda_worker.process
        if process:
            logger.info("[main] conda_manager working...")
            exit_code = await asyncio.to_thread(process.wait)
            logger.error(f"[main] conda_manager exited with code {exit_code}")
            sys.exit(exit_code)
        else:
            logger.error("[main] No process found")
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        if model_handler is not None and model_handler.conda_worker is not None:
            model_handler.conda_worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
