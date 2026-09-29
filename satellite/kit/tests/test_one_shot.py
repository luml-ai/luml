import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.helpers import deployment_record, task_record


def test_one_shot_satellite_uses_lower_tiers_against_a_separate_platform(
    tmp_path: Path,
) -> None:
    token = "one-shot-token"
    state_path = tmp_path / "platform.json"
    state_path.write_text(
        json.dumps(
            {
                "token": token,
                "deployments": [deployment_record()],
                "tasks": [task_record()],
            }
        ),
        encoding="utf-8",
    )
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from luml_satellite.testing.fake_platform import main; main()",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--state",
            str(state_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_server(base_url, server)
        completed = subprocess.run(
            [sys.executable, "-c", _ONE_SHOT_SCRIPT, base_url, token],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "one-shot deployment active"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_server(base_url: str, server: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if server.poll() is not None:
            stdout, stderr = server.communicate()
            pytest.fail(f"fake platform exited during startup:\n{stdout}\n{stderr}")
        try:
            response = httpx.get(f"{base_url}/satellites/v1/contract", timeout=0.2)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.02)
    pytest.fail("fake platform did not start within ten seconds")


_ONE_SHOT_SCRIPT = r"""
import asyncio
import builtins
import sys

original_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "fastapi" or name.startswith("fastapi."):
        raise AssertionError(f"unexpected optional import: {name}")
    if name == "opentelemetry" or name.startswith("opentelemetry."):
        raise AssertionError(f"unexpected optional import: {name}")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import

from luml_satellite import (
    ArtifactResolver,
    Convergence,
    NoServingPlacement,
    PlatformClient,
    SatelliteQueueTask,
    TokenDeriver,
    derive_capabilities,
    pair_satellite,
)
from luml_satellite.testing import FakeDriver


async def run() -> None:
    base_url, token = sys.argv[1:]
    driver = FakeDriver(workload_listing=False)
    capabilities = derive_capabilities(
        supported_variants=driver.supported_variants,
        supported_tags_combinations=driver.supported_tag_combinations,
        settings_type=driver.settings_type,
        serves_deployments=False,
    )
    async with PlatformClient(base_url, token) as platform:
        await pair_satellite(
            platform,
            kind=driver.kind,
            capabilities=capabilities,
            base_url="http://satellite",
        )
        convergence = Convergence(
            platform,
            driver,
            ArtifactResolver(
                platform,
                TokenDeriver(token),
                satellite_address="http://satellite",
            ),
            serving=NoServingPlacement(),
        )
        task_data = (await platform.list_tasks("pending"))[0]
        await convergence.handle_task(SatelliteQueueTask.model_validate(task_data))
        deployment_id = str(task_data["payload"]["deployment_id"])
        deployment = await platform.get_deployment(deployment_id)
        finished_tasks = await platform.list_tasks("done")

    assert deployment.status == "active"
    assert deployment.inference_url == f"http://fake/{deployment_id}"
    assert [task["id"] for task in finished_tasks] == [task_data["id"]]
    assert not any(
        name == "fastapi"
        or name.startswith("fastapi.")
        or name == "opentelemetry"
        or name.startswith("opentelemetry.")
        for name in sys.modules
    )
    print("one-shot deployment active")


asyncio.run(run())
"""
