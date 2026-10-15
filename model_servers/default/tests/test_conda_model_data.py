import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from conda_manager import ModelCondaManager

WORKER_SCRIPT = Path(__file__).resolve().parents[1] / "conda_worker.py"


@pytest.fixture
def large_model_data() -> dict:
    return {
        "model_name": "large_模型",
        "manifest": {"inputs": [{"name": "features"}]},
        "dtypes_schemas": {},
        "reference_profile": {
            f"feature_{index}": {
                "histogram": [index / 123.456 for index in range(50)],
                "quantiles": [index / 987.654 for index in range(99)],
            }
            for index in range(100)
        },
    }


def test_large_model_data_crosses_a_real_process_boundary(
    tmp_path: Path, large_model_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert len(json.dumps(large_model_data).encode()) > 200_000
    launcher = tmp_path / "micromamba"
    launcher.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[5:]])\n"
    )
    launcher.chmod(0o700)
    received = tmp_path / "received.json"
    metadata_path = tmp_path / "metadata-path.txt"
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(metadata_path)!r}).write_text(sys.argv[3])\n"
        "with open(sys.argv[3], encoding='utf-8') as stream:\n"
        "    data = json.load(stream)\n"
        f"pathlib.Path({str(received)!r}).write_text(json.dumps(data))\n"
    )
    manager = ModelCondaManager(
        "model-env", SimpleNamespace(_exe=str(launcher)), str(tmp_path), large_model_data
    )
    manager.worker_script = worker

    def wait_for_worker() -> None:
        assert manager.process is not None
        assert manager.process.wait(timeout=10) == 0
        assert Path(metadata_path.read_text()).exists()

    monkeypatch.setattr(manager, "_wait_for_health_check", wait_for_worker)
    try:
        process = manager.start()
        assert process.returncode == 0
        assert json.loads(received.read_text()) == large_model_data
        assert not Path(metadata_path.read_text()).exists()
    finally:
        manager.stop()


@pytest.mark.parametrize("failure", ["spawn", "health"])
def test_metadata_file_is_removed_when_startup_fails(failure: str) -> None:
    manager = ModelCondaManager("model-env", SimpleNamespace(_exe="micromamba"), "/model")
    metadata_paths: list[Path] = []
    process = Mock(stderr=[])

    def spawn(cmd: list[str], **kwargs: object) -> Mock:
        metadata_paths.append(Path(cmd[-1]))
        assert json.loads(metadata_paths[-1].read_text()) == {}
        if failure == "spawn":
            raise OSError("cannot spawn worker")
        return process

    with (
        patch("conda_manager.subprocess.Popen", side_effect=spawn),
        patch.object(manager, "_wait_for_health_check", side_effect=RuntimeError("unhealthy")),
        pytest.raises((OSError, RuntimeError)),
    ):
        manager.start()

    assert metadata_paths
    assert not metadata_paths[0].exists()
    if failure == "health":
        process.terminate.assert_called_once()
        process.wait.assert_called_once()


@pytest.mark.parametrize("has_metadata", [True, False])
async def test_worker_loads_metadata_and_preserves_endpoints(
    tmp_path: Path, large_model_data: dict, has_metadata: bool
) -> None:
    metadata = tmp_path / "model-data.json"
    metadata.write_text(json.dumps(large_model_data), encoding="utf-8")
    argv = [str(WORKER_SCRIPT), str(tmp_path), "8080"]
    if has_metadata:
        argv.append(str(metadata))
    with (
        patch.object(sys, "argv", argv),
        patch("fnnx.runtime.Runtime"),
        patch("fnnx.device.DeviceMap"),
        patch("fnnx.handlers.local.LocalHandlerConfig"),
        patch("openapi_generator.OpenAPIGenerator") as openapi,
    ):
        namespace = runpy.run_path(str(WORKER_SCRIPT))

    expected = large_model_data if has_metadata else {}
    assert namespace["model_data"] == expected
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=namespace["app"]), base_url="http://worker"
    ) as client:
        manifest = await client.get("/manifest")
        profile = await client.get("/reference_profile")
    assert manifest.status_code == 200
    assert manifest.json() == expected.get("manifest", {})
    assert profile.status_code == 200
    assert profile.json() == expected.get("reference_profile", {})
    if has_metadata:
        assert openapi.call_args.kwargs == {
            "title": "LARGE 模型",
            "description": "API for large_模型 model",
            "manifest": large_model_data["manifest"],
            "dtypes_schemas": large_model_data["dtypes_schemas"],
        }
    else:
        openapi.assert_not_called()


@pytest.mark.parametrize("contents", [None, "{invalid json"])
def test_worker_exits_if_metadata_cannot_be_loaded(tmp_path: Path, contents: str | None) -> None:
    metadata = tmp_path / "model-data.json"
    if contents is not None:
        metadata.write_text(contents, encoding="utf-8")
    with (
        patch.object(sys, "argv", [str(WORKER_SCRIPT), str(tmp_path), "8080", str(metadata)]),
        pytest.raises(SystemExit) as error,
    ):
        runpy.run_path(str(WORKER_SCRIPT))
    assert error.value.code == 1
