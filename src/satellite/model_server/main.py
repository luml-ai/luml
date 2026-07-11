import asyncio
import logging
import sys

from handlers.model_handler import ModelHandler

logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        model_handler = ModelHandler()
    except Exception as error:
        logger.error(f"[main] Failed to initialize ModelHandler: {error}")
        sys.exit(1)

    process = model_handler.conda_worker.process
    if process:
        logger.info("[main] conda_manager working...")
        exit_code = await asyncio.to_thread(process.wait)
        logger.error(f"[main] conda_manager exited with code {exit_code}")
        sys.exit(exit_code)
    else:
        logger.error("[main] No process found")


if __name__ == "__main__":
    asyncio.run(main())
