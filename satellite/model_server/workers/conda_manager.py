import contextlib
import json
import logging
import socket
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [web_worker] %(message)s"
)
logger = logging.getLogger(__name__)


class ModelCondaManager:
    def __init__(self, model_envs: dict, extracted_path: str) -> None:
        self.model_envs = model_envs
        self.extracted_path = extracted_path
        self.process = None
        self.port = None
        self.worker_script = Path(__file__).parent / "conda_worker.py"

    @staticmethod
    def _get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    @property
    def worker_url(self) -> str | None:
        return f"http://127.0.0.1:{self.port}" if self.port else None

    def get_env_name(self) -> str:
        if self.model_envs["path"]:
            env_path = self.model_envs["path"]
            return env_path.split("/")[-1]
        else:
            return self.model_envs["name"]

    def start(self) -> subprocess.Popen:
        self.port = self._get_free_port()
        env_name = self.get_env_name()

        cmd = [
            self.model_envs["manager"]._exe,
            "run",
            "-n",
            env_name,
            "python",
            str(self.worker_script),
            self.extracted_path,
            str(self.port),
        ]

        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        try:
            self._wait_for_ready_signal()
            self._wait_for_health_check()
            logger.info("[START] Worker health check passed")
            return self.process
        except Exception as error:
            logger.error(f"[START] Failed to start worker: {error}")
            if self.process:
                self.process.terminate()
            raise RuntimeError(f"Failed to start worker: {error}") from error

    def _wait_for_ready_signal(self) -> None:
        while True:
            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read()
                logger.error(f"[START] Worker process exited unexpectedly. Stderr: {stderr}")
                raise RuntimeError(f"Worker process exited unexpectedly. Stderr: {stderr}")

            status_msg = json.loads(line.strip())

            if status_msg.get("status") == "ready":
                logger.info("[START] Worker ready")
                break
            elif status_msg.get("status") == "error":
                logger.error(f"[START] Worker initialization failed: {status_msg.get('error')}")
                raise RuntimeError(f"Worker initialization failed: {status_msg.get('error')}")

    def _wait_for_health_check(self, timeout: int = 45) -> None:
        start_time = time.time()

        with httpx.Client() as client:
            while time.time() - start_time < timeout:
                with contextlib.suppress(Exception):
                    response = client.get(f"{self.worker_url}/health", timeout=5.0)
                    if response.status_code == 200:
                        return
                time.sleep(0.5)

        raise RuntimeError(f"Worker health check failed after {timeout}s")

    def is_alive(self) -> bool:
        return self.process and self.process.poll() is None

    async def compute(self, inputs: dict, dynamic_attributes: dict) -> Any:  # noqa: ANN401
        if not self.is_alive():
            raise RuntimeError(
                f"Worker process died unexpectedly. Stderr: {self.process.stderr.read()}"
            )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.worker_url}/compute",
                    json={"inputs": inputs, "dynamic_attributes": dynamic_attributes},
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("error", response.text)
                    except Exception:
                        error_detail = response.text
                    raise RuntimeError(f"Worker error {response.status_code}: {error_detail}")

        except Exception as error:
            raise RuntimeError(
                f"Worker communication failed: {error}\nTraceback: {traceback.format_exc()}"
            ) from error

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        self.port = None
