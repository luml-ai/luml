import contextlib
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [web_worker] %(message)s"
)
logger = logging.getLogger(__name__)


class ModelCondaManager:
    def __init__(
        self,
        env_name: str,
        env_manager: Any,  # noqa: ANN401
        extracted_path: str,
        model_data: dict | None = None,
    ) -> None:
        self.env_name = env_name
        self.env_manager = env_manager
        self.extracted_path = extracted_path
        self.model_data = model_data or {}
        self.process: subprocess.Popen | None = None
        self.port: int | None = 8080
        self.worker_script = Path(__file__).parent / "conda_worker.py"

    @property
    def worker_url(self) -> str | None:
        return f"http://0.0.0.0:{self.port}" if self.port else None

    def _wait_for_health_check(self, timeout: int = 90) -> None:
        with httpx.Client() as client:
            for _ in range(timeout):
                with contextlib.suppress(Exception):
                    response = client.get(f"{self.worker_url}/healthz", timeout=5.0)
                    if response.status_code == 200:
                        return
                time.sleep(1)

        raise RuntimeError(f"Worker health check failed after {timeout}s")

    def start(self) -> subprocess.Popen:
        cmd = [
            self.env_manager._exe,
            "run",
            "-n",
            self.env_name,
            "python",
            str(self.worker_script),
            self.extracted_path,
            str(self.port),
            json.dumps(self.model_data),
        ]

        self.process = subprocess.Popen(cmd, stdout=None, stderr=None, text=True)

        try:
            self._wait_for_health_check()
            logger.info("[START] Worker health check passed")
            return self.process
        except Exception as error:
            logger.error(f"[START] Failed to start worker: {error}")
            if self.process:
                self.process.terminate()
            raise RuntimeError(f"Failed to start worker: {error}") from error

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        self.port = None
