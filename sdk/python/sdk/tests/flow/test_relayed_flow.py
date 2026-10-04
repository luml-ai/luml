import json
import logging
import os
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import FrameType

import httpx
import pytest

import luml.flow as flow_module
from luml.flow import RelayedFlow, RelayedFlowError
from tests.flow.fakes import (
    APP_URL,
    FLOW_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    SESSION_ID,
    FakeClients,
    FakeServing,
    free_port,
    local_server,
    write_stub_lumlflow,
)

SDK_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def luml_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUML_API_KEY", "luml_test_key")
    monkeypatch.setenv("LUML_BASE_URL", "http://127.0.0.1:9")


@pytest.fixture(autouse=True)
def restore_termination_handler() -> Iterator[None]:
    original = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, original)


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch) -> FakeClients:
    fake = FakeClients()
    monkeypatch.setattr(flow_module, "LumlClient", fake)
    return fake


@pytest.fixture
def serving(monkeypatch: pytest.MonkeyPatch) -> FakeServing:
    fake = FakeServing()
    monkeypatch.setattr(flow_module, "serve_session", fake)
    return fake


@pytest.fixture
def port() -> int:
    return free_port()


@pytest.fixture
def stub_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Puts a stub `lumlflow` alone on the path; yields its record of starts."""
    record = tmp_path / "lumlflow-starts.jsonl"
    stub_directory = tmp_path / "bin"
    write_stub_lumlflow(stub_directory)
    monkeypatch.setenv("PATH", str(stub_directory))
    monkeypatch.setenv("STUB_LUMLFLOW_RECORD", str(record))
    yield record
    for start in _stub_starts(record):
        if _alive(start["pid"]):
            os.kill(start["pid"], signal.SIGKILL)


@pytest.fixture
def no_lumlflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def _stub_starts(record: Path) -> list[dict]:
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text().splitlines()]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _answers(port: int) -> bool:
    try:
        httpx.get(f"http://127.0.0.1:{port}/api/auth/status", trust_env=False)
    except httpx.ConnectError:
        return False
    return True


@pytest.mark.usefixtures("serving")
def test_started_lumlflow_is_exposed_and_stopped_with_the_block(
    clients: FakeClients,
    serving: FakeServing,
    port: int,
    stub_record: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with RelayedFlow(
        "training",
        organization="Lab",
        orbit="Experiments",
        store_path="sqlite://./runs",
        port=port,
    ) as flow:
        assert _answers(port)
        assert clients.flows.exposed == ["training"]
        assert clients.flows.removed == []
        assert serving.served == [(SESSION_ID, ORGANIZATION_ID, ORBIT_ID)]
        assert flow.app_url == APP_URL
        assert f"Flow training is live at {APP_URL}" in capsys.readouterr().out

    assert clients.setups == [{"organization": "Lab", "orbit": "Experiments"}]
    assert clients.flows.removed == [FLOW_ID]
    assert serving.cancelled == 1
    [start] = _stub_starts(stub_record)
    assert start["argv"] == [
        "ui",
        "--port",
        str(port),
        "--no-browser",
        "--path",
        "sqlite://./runs",
    ]
    assert not _alive(start["pid"])
    assert not _answers(port)


@pytest.mark.usefixtures("no_lumlflow")
def test_running_lumlflow_is_exposed_and_left_running(
    clients: FakeClients, serving: FakeServing, port: int
) -> None:
    with local_server(port, answers_as_lumlflow=True):
        with RelayedFlow("training", port=port):
            assert clients.flows.exposed == ["training"]

        assert clients.flows.removed == [FLOW_ID]
        assert serving.cancelled == 1
        assert _answers(port)


@pytest.mark.usefixtures("serving")
def test_port_in_use_fails_before_anything_is_created(
    clients: FakeClients, port: int, stub_record: Path
) -> None:
    with (
        local_server(port, answers_as_lumlflow=False),
        pytest.raises(RelayedFlowError, match=f"Port {port} is in use"),
    ):
        RelayedFlow("training", port=port).start()

    assert clients.flows.exposed == []
    assert _stub_starts(stub_record) == []


@pytest.mark.usefixtures("serving", "no_lumlflow")
def test_missing_lumlflow_says_to_install_it(clients: FakeClients, port: int) -> None:
    with pytest.raises(RelayedFlowError, match="install lumlflow"):
        RelayedFlow("training", port=port).start()

    assert clients.flows.exposed == []


@pytest.mark.usefixtures("stub_record")
def test_explicit_start_and_stop_across_cells(
    clients: FakeClients, serving: FakeServing, port: int
) -> None:
    flow = RelayedFlow("training", port=port)

    assert flow.start() == APP_URL
    assert clients.flows.removed == []
    assert serving.cancelled == 0

    flow.stop()
    flow.stop()

    assert clients.flows.removed == [FLOW_ID]
    assert serving.cancelled == 1
    with pytest.raises(RelayedFlowError, match="already started"):
        flow.start()


@pytest.mark.usefixtures("serving", "stub_record")
def test_default_name_is_the_host_name(clients: FakeClients, port: int) -> None:
    for _ in range(2):
        with RelayedFlow(port=port):
            pass

    assert clients.flows.exposed == [socket.gethostname()] * 2


@pytest.mark.usefixtures("stub_record")
def test_failed_serving_raises_its_cause_and_cleans_up(
    clients: FakeClients, serving: FakeServing, port: int
) -> None:
    serving.failure = RuntimeError("the relay refused the agent")

    with pytest.raises(RuntimeError, match="the relay refused the agent"):
        RelayedFlow("training", port=port).start()

    assert clients.flows.removed == [FLOW_ID]
    assert not _answers(port)


@pytest.mark.usefixtures("stub_record")
def test_unreachable_luml_on_stop_still_stops_local_parts(
    clients: FakeClients,
    serving: FakeServing,
    port: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clients.flows.remove_error = httpx.ConnectError("LUML is down")

    with caplog.at_level(logging.WARNING), RelayedFlow("training", port=port):
        pass

    assert "ends by silence" in caplog.text
    assert serving.cancelled == 1
    assert not _answers(port)


@pytest.mark.usefixtures("serving", "stub_record")
def test_termination_stops_the_flow_once_and_chains(
    clients: FakeClients, port: int
) -> None:
    received: list[int] = []

    def previous_handler(signum: int, frame: FrameType | None) -> None:
        received.append(signum)

    signal.signal(signal.SIGTERM, previous_handler)
    flow = RelayedFlow("training", port=port)
    flow.start()
    handler = signal.getsignal(signal.SIGTERM)
    assert callable(handler)
    assert handler != previous_handler

    handler(signal.SIGTERM, None)
    flow.stop()

    assert clients.flows.removed == [FLOW_ID]
    assert received == [signal.SIGTERM]
    assert signal.getsignal(signal.SIGTERM) == previous_handler


@pytest.mark.usefixtures("clients", "serving", "stub_record")
def test_no_interruption_handler_is_installed(port: int) -> None:
    before = signal.getsignal(signal.SIGINT)

    with RelayedFlow("training", port=port):
        assert signal.getsignal(signal.SIGINT) == before


EXITING_SCRIPT = """
import os, signal, sys, time

import luml.flow
from tests.flow.fakes import FakeClients, FakeServing


def record_removal(flow_id):
    with open(sys.argv[1], "a") as record:
        record.write("removed\\n")


clients = FakeClients()
clients.flows.on_remove = record_removal
luml.flow.LumlClient = clients
luml.flow.serve_session = FakeServing()
luml.flow.RelayedFlow("training", port=int(sys.argv[2])).start()
if sys.argv[3] == "terminate":
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(10)
raise RuntimeError("training failed")
"""


@pytest.mark.parametrize(
    ("ending", "returncode"),
    [("terminate", -signal.SIGTERM), ("error", 1)],
)
def test_process_end_removes_the_flow_once_and_stops_lumlflow(
    ending: str, returncode: int, port: int, stub_record: Path, tmp_path: Path
) -> None:
    removals = tmp_path / "removals"

    result = subprocess.run(
        [sys.executable, "-c", EXITING_SCRIPT, str(removals), str(port), ending],
        cwd=SDK_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == returncode, result.stderr
    assert removals.read_text() == "removed\n"
    [start] = _stub_starts(stub_record)
    assert not _alive(start["pid"])


def test_flow_module_needs_the_flow_extra() -> None:
    script = (
        "import sys\n"
        "sys.modules['luml_tunnel'] = None\n"
        "import luml\n"
        "print('sdk imported')\n"
        "import luml.flow\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )

    assert result.returncode != 0
    assert "sdk imported" in result.stdout
    assert "install luml_sdk[flow]" in result.stderr
