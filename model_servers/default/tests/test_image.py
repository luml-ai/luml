import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RANDOM_UID = 24680

_EXTRACT_SCRIPT = """
import json
import os
import shutil
import stat
from pathlib import Path

from handlers.file_handler import FileHandler
from handlers.model_handler import ModelHandler


class MountedArchiveHandler(FileHandler):
    def __init__(self) -> None:
        self.downloaded = False

    def download_file(self, url: str, file_path: str | Path) -> str:
        self.downloaded = True
        shutil.copyfile('/fixture/model.tar', file_path)
        return str(file_path)


file_handler = MountedArchiveHandler()
handler = ModelHandler.__new__(ModelHandler)
handler._model_url = 'https://fixtures.invalid/model.tar'
handler._agent = None
handler._models_cache_dir = Path('/app/models')
handler._file_handler = file_handler
extracted = Path(handler._get_or_extract_model())
models_stat = Path('/app/models').stat()
extracted_stat = extracted.stat()
print(json.dumps({
    'artifact_gid': extracted_stat.st_gid,
    'artifact_uid': extracted_stat.st_uid,
    'downloaded': file_handler.downloaded,
    'home': os.environ.get('HOME'),
    'manifest': (extracted / 'manifest.json').read_text(),
    'mamba_root': os.environ.get('MAMBA_ROOT_PREFIX'),
    'models_gid': models_stat.st_gid,
    'models_mode': stat.S_IMODE(models_stat.st_mode),
    'models_uid': models_stat.st_uid,
    'uid': os.getuid(),
    'uv_cache': os.environ.get('UV_CACHE_DIR'),
}))
"""

_ENV_LOCATION_SCRIPT = """
import json
import os
from pathlib import Path

root = Path(os.environ['MAMBA_ROOT_PREFIX'])
envs = sorted(str(path) for path in (root / 'envs').iterdir() if path.is_dir())
print(json.dumps({'envs': envs, 'root': str(root)}))
"""


@dataclass(frozen=True)
class RunningModel:
    container_id: str
    health_url: str


def _run(
    command: list[str],
    *,
    check: bool = True,
    timeout: float = 900,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


@pytest.fixture(scope="session")
def docker_cli() -> str:
    executable = shutil.which("docker")
    if executable is None:
        pytest.skip("Docker is not installed; model-server image tests were not run")

    info = _run([executable, "info"], check=False, timeout=30)
    if info.returncode != 0:
        pytest.skip("Docker daemon is unavailable; model-server image tests were not run")
    return executable


@pytest.fixture(scope="session")
def model_server_image(docker_cli: str) -> Iterator[str]:
    image = f"luml-model-server-test:{uuid4().hex}"
    _run([docker_cli, "build", "--tag", image, str(PROJECT_ROOT)])
    try:
        yield image
    finally:
        _run([docker_cli, "image", "rm", "--force", image], check=False, timeout=60)


def _make_archive(tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"name": "synthetic"}')
    archive = tmp_path / "model.tar"
    with tarfile.open(archive, "w") as tar:
        tar.add(manifest, arcname="manifest.json")
    return archive


def _extract_with_image(
    docker_cli: str,
    image: str,
    *,
    archive: Path | None,
    volume: str | None = None,
) -> dict[str, object]:
    command = [
        docker_cli,
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        f"{RANDOM_UID}:0",
    ]
    if archive is not None:
        command.extend(
            [
                "--mount",
                f"type=bind,source={archive},target=/fixture/model.tar,readonly",
            ]
        )
    if volume is not None:
        command.extend(["--mount", f"type=volume,source={volume},target=/app/models"])
    command.extend(
        [
            "--entrypoint",
            "/app/.venv/bin/python",
            image,
            "-c",
            _EXTRACT_SCRIPT,
        ]
    )

    result = _run(command, timeout=120)
    raw_payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert isinstance(raw_payload, dict)
    return {str(key): value for key, value in raw_payload.items()}


def _assert_writable_models_directory(payload: dict[str, object]) -> None:
    assert payload["uid"] == RANDOM_UID
    assert payload["models_uid"] == 10001
    assert payload["models_gid"] == 0
    mode = payload["models_mode"]
    assert isinstance(mode, int)
    assert mode & 0o020
    assert payload["artifact_gid"] == 0
    assert payload["artifact_uid"] == RANDOM_UID
    assert payload["manifest"] == '{"name": "synthetic"}'
    assert payload["home"] == "/app"
    assert payload["mamba_root"] == "/app/.micromamba"
    assert payload["uv_cache"] == "/app/.cache/uv"


def test_image_unpacks_a_synthetic_archive_as_an_arbitrary_user(
    docker_cli: str,
    model_server_image: str,
    tmp_path: Path,
) -> None:
    payload = _extract_with_image(
        docker_cli,
        model_server_image,
        archive=_make_archive(tmp_path),
    )

    _assert_writable_models_directory(payload)
    assert payload["downloaded"] is True


def test_named_volume_is_writable_and_reuses_the_cached_artifact(
    docker_cli: str,
    model_server_image: str,
    tmp_path: Path,
) -> None:
    volume = f"luml-model-server-test-{uuid4().hex}"
    _run([docker_cli, "volume", "create", volume])
    try:
        first = _extract_with_image(
            docker_cli,
            model_server_image,
            archive=_make_archive(tmp_path),
            volume=volume,
        )
        second = _extract_with_image(
            docker_cli,
            model_server_image,
            archive=None,
            volume=volume,
        )
    finally:
        _run([docker_cli, "volume", "rm", "--force", volume], check=False, timeout=60)

    _assert_writable_models_directory(first)
    _assert_writable_models_directory(second)
    assert first["downloaded"] is True
    assert second["downloaded"] is False


def _container_logs(docker_cli: str, container_id: str) -> str:
    return _run([docker_cli, "logs", container_id], check=False, timeout=30).stdout


def _wait_until_healthy(docker_cli: str, container_id: str, health_url: str) -> None:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        state = _run(
            [docker_cli, "inspect", "--format", "{{.State.Running}}", container_id],
            check=False,
            timeout=30,
        )
        if state.returncode != 0 or state.stdout.strip() != "true":
            logs = _container_logs(docker_cli, container_id)
            pytest.fail(f"Model-server container exited before becoming healthy:\n{logs}")
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (TimeoutError, urllib.error.URLError):
            pass
        time.sleep(1)

    logs = _container_logs(docker_cli, container_id)
    pytest.fail(f"Model-server health route did not become ready:\n{logs}")


@pytest.fixture(scope="session")
def running_loadable_model(
    docker_cli: str,
    model_server_image: str,
) -> Iterator[RunningModel]:
    artifact_url = os.getenv("MODEL_SERVER_TEST_ARTIFACT_URL")
    if not artifact_url:
        pytest.skip(
            "MODEL_SERVER_TEST_ARTIFACT_URL is not set; loadable-model health and "
            "micromamba checks were not run"
        )

    started = _run(
        [
            docker_cli,
            "run",
            "--detach",
            "--user",
            f"{RANDOM_UID}:0",
            "--env",
            f"MODEL_ARTIFACT_URL={artifact_url}",
            "--env",
            "MODEL_NAME=image-integration-test",
            "--publish",
            "127.0.0.1::8080",
            model_server_image,
        ]
    )
    container_id = started.stdout.strip()
    try:
        published = _run([docker_cli, "port", container_id, "8080/tcp"], timeout=30)
        host_port = published.stdout.strip().rsplit(":", maxsplit=1)[-1]
        health_url = f"http://127.0.0.1:{host_port}/healthz"
        _wait_until_healthy(docker_cli, container_id, health_url)
        yield RunningModel(container_id=container_id, health_url=health_url)
    finally:
        _run([docker_cli, "rm", "--force", container_id], check=False, timeout=60)


def test_health_route_with_a_supplied_loadable_model(running_loadable_model: RunningModel) -> None:
    with urllib.request.urlopen(running_loadable_model.health_url, timeout=5) as response:
        payload = json.loads(response.read())

    assert response.status == 200
    assert payload == {"status": "healthy"}


def test_model_environment_is_created_under_app(
    docker_cli: str,
    running_loadable_model: RunningModel,
) -> None:
    result = _run(
        [
            docker_cli,
            "exec",
            running_loadable_model.container_id,
            "/app/.venv/bin/python",
            "-c",
            _ENV_LOCATION_SCRIPT,
        ],
        timeout=30,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])

    assert payload["root"] == "/app/.micromamba"
    assert payload["envs"]
    assert all(path.startswith("/app/.micromamba/envs/") for path in payload["envs"])
