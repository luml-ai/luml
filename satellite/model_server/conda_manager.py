import contextlib
import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class ModelCondaManager:
    WORKER_LOGS_LINES = 50
    THREAD_SHUTDOWN_TIMEOUT = 2

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
        self._error_output: list[str] = []
        self._stderr_monitor_thread: threading.Thread | None = None

    @property
    def worker_url(self) -> str | None:
        return f"http://0.0.0.0:{self.port}" if self.port else None

    def _monitor_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return

        try:
            for line in self.process.stderr:
                line = line.strip()
                if line:
                    self._error_output.append(line)
                    logger.error(f"[conda_worker] {line}")

            if self.process:
                exit_code = self.process.poll()
                if exit_code is not None and exit_code != 0:
                    logger.error(f"Conda worker process exited with code {exit_code}")

        except Exception as e:
            logger.error(f"Error monitoring stderr: {e}")

    def _check_process_status(self) -> None:
        if not self.process:
            return

        exit_code = self.process.poll()
        if exit_code is not None and exit_code != 0:
            error_msg = f"Conda worker process exited with code {exit_code}"
            if self._error_output:
                error_msg += "\n" + "\n".join(self._error_output[-self.WORKER_LOGS_LINES :])
            raise RuntimeError(error_msg)

    def _wait_for_health_check(self, timeout: int = 90) -> None:
        with httpx.Client() as client:
            for _ in range(timeout):
                self._check_process_status()

                with contextlib.suppress(Exception):
                    response = client.get(f"{self.worker_url}/healthz", timeout=5.0)
                    if response.status_code == 200:
                        return
                time.sleep(1)

        self._check_process_status()
        raise RuntimeError(f"Worker health check failed after {timeout}s")

    def start(self) -> subprocess.Popen:
        cmd = [
            self.env_manager._exe,
            "run",
            "-n",
            self.env_name,
            "python",
            "-u",
            str(self.worker_script),
            self.extracted_path,
            str(self.port),
            json.dumps(self.model_data),
        ]

        self.process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )

        self._stderr_monitor_thread = threading.Thread(target=self._monitor_stderr, daemon=True)
        self._stderr_monitor_thread.start()

        try:
            self._wait_for_health_check()
            return self.process
        except Exception as error:
            if self.process:
                self.process.terminate()
                self.process.wait()
            raise RuntimeError(f"Failed to start worker: {error}") from error

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

        if self._stderr_monitor_thread and self._stderr_monitor_thread.is_alive():
            self._stderr_monitor_thread.join(timeout=self.THREAD_SHUTDOWN_TIMEOUT)
            self._stderr_monitor_thread = None

        self.port = None
