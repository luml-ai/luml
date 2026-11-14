import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_python_base_is_digest_pinned_and_shared_between_build_and_runtime() -> None:
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text()
    assert re.search(
        r"^FROM python:3\.14-slim-bookworm@sha256:[a-f0-9]{64} AS base$",
        dockerfile,
        re.MULTILINE,
    )
    assert "FROM base AS builder" in dockerfile
    assert "FROM base AS runtime" in dockerfile


@pytest.fixture(scope="module")
def backend_image() -> Iterator[tuple[str, str]]:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker is not installed; backend image checks were not run")
    result = subprocess.run(
        [docker, "info"], capture_output=True, check=False, timeout=30
    )
    if result.returncode != 0:
        pytest.skip("Docker daemon is unavailable; backend image checks were not run")
    image = f"luml-backend-test:{uuid4().hex}"
    subprocess.run(
        [docker, "build", "--tag", image, str(BACKEND_ROOT)], check=True, timeout=900
    )
    try:
        yield docker, image
    finally:
        subprocess.run(
            [docker, "image", "rm", "--force", image], check=False, timeout=60
        )


def test_runtime_is_non_root_without_compilers_or_dev_dependencies(
    backend_image: tuple[str, str],
) -> None:
    docker, image = backend_image
    probe = """
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import _cffi_backend
import asyncpg
import cryptography.hazmat.bindings._rust
import uvicorn
from argon2 import PasswordHasher

assert os.getuid() == 10001
assert all(shutil.which(name) is None for name in ('gcc', 'g++', 'make'))
for package in ('build-essential', 'libffi-dev', 'libssl-dev'):
    result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', package],
                            capture_output=True, text=True)
    assert result.stdout.strip() != 'install ok installed'
for name in ('mypy', 'pytest', 'ruff'):
    assert importlib.util.find_spec(name) is None
assert Path('/app/luml/server.py').is_file()
assert Path('/app/migrations/env.py').is_file()
assert Path('/app/alembic.ini').is_file()
passwords = PasswordHasher()
assert passwords.verify(passwords.hash('image-check'), 'image-check')
print(json.dumps({'uid': os.getuid()}))
"""
    result = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "python",
            image,
            "-c",
            probe,
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=60,
    )
    assert json.loads(result.stdout)["uid"] == 10001


def test_runtime_commands_work_offline_as_the_default_user(
    backend_image: tuple[str, str],
) -> None:
    docker, image = backend_image
    for command in (["uvicorn", "--help"], ["uv", "run", "alembic", "--help"]):
        result = subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--env",
                "UV_OFFLINE=1",
                "--entrypoint",
                command[0],
                image,
                *command[1:],
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr


def test_default_command_starts_the_api_without_network_access(
    backend_image: tuple[str, str], tmp_path: Path
) -> None:
    docker, image = backend_image
    server = tmp_path / "server.py"
    server.write_text(
        "import os\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.on_event('startup')\n"
        "async def started():\n"
        "    print('started', flush=True)\n"
        "    os._exit(0)\n"
    )
    result = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--env",
            "UV_OFFLINE=1",
            "--mount",
            f"type=bind,source={server},target=/app/luml/server.py,readonly",
            image,
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=60,
    )
    assert result.stdout.strip() == "started"
