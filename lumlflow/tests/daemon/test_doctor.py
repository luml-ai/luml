import json
import logging
import os
from pathlib import Path

import pytest
from lumlflow import __version__
from lumlflow.cli import NON_LOOPBACK_WARNING, app
from lumlflow.flow.daemon import client, daemon_log, harnesses, workspace
from lumlflow.flow.daemon import doctor as diagnostics
from lumlflow.flow.daemon.workspace import DaemonRecord
from typer.testing import CliRunner

from tests.daemon.helpers import make_workspace


def test_doctor_reports_the_daemon_directory_environment_and_owned_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    monkeypatch.setattr(
        harnesses.HarnessService,
        "owned_entries",
        lambda _self: [
            {
                "id": "codex",
                "display_name": "Codex CLI",
                "state": "set up",
                "config_path": str(tmp_path / "home" / ".codex" / "config.toml"),
            }
        ],
    )

    with client.connect(root) as live:
        live.call("flow.open", {"flow": "churn"})
        result = CliRunner().invoke(app, ["doctor", str(root), "--json"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["directory"] == str(root)
    assert report["state_directory"] == {
        "path": str(workspace.state_dir()),
        "local": True,
    }
    assert report["record"] == {
        "pid": live.record.pid,
        "instance_id": live.record.instance_id,
        "socket_address": f"127.0.0.1:{live.record.port}",
        "web_host": live.record.web_host,
        "web_port": live.record.web_port,
        "tracker_store": live.record.tracker_store,
        "version": live.record.version,
    }
    assert "token" not in report["record"]
    assert report["lock"] == "held"
    assert report["handshake"] == {
        "status": "answering",
        "instance_id": live.record.instance_id,
    }
    assert report["log_path"] == str(workspace.log_path())
    assert report["interpreter"]["path"]
    assert report["interpreter"]["source"] == "lumlflow"
    assert report["tracker_store"] == live.record.tracker_store
    assert report["flow_stores"]["count"] == 1
    assert report["flow_stores"]["disk_bytes"] > 0
    assert report["harness_entries"][0]["id"] == "codex"
    assert report["warnings"] == []

    shown = CliRunner().invoke(app, ["doctor", str(root)])
    assert shown.exit_code == 0, shown.output
    for field in (
        "state directory",
        "daemon record",
        "lock",
        "handshake",
        "daemon log",
        "interpreter",
        "tracker store",
        "flow stores",
        "owned harness entries",
    ):
        assert field in shown.output


def test_doctor_warns_for_a_running_non_loopback_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    record = DaemonRecord(
        pid=os.getpid(),
        instance_id="remote",
        port=1234,
        token="secret",
        web_host="0.0.0.0",
        web_port=5000,
        tracker_store=str(tmp_path / "experiments"),
        version=__version__,
    )
    workspace.write_record(record)
    monkeypatch.setattr(workspace, "lock_held", lambda: True)
    monkeypatch.setattr(client, "is_alive", lambda _record: True)
    monkeypatch.setattr(harnesses.HarnessService, "owned_entries", lambda _self: [])

    result = CliRunner().invoke(app, ["doctor", str(root)])
    workspace.clear_record(instance_id=record.instance_id)

    assert result.exit_code == 0, result.output
    assert NON_LOOPBACK_WARNING in result.output


@pytest.mark.parametrize(
    ("recorded", "held", "alive", "status"),
    [
        (False, False, False, "not answering"),
        (True, True, False, "not answering"),
        (True, False, False, "stale record"),
    ],
)
def test_doctor_distinguishes_absent_hung_and_stale_daemons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recorded: bool,
    held: bool,
    alive: bool,
    status: str,
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    record = DaemonRecord(
        pid=1234,
        instance_id="snapshot",
        port=1234,
        token="secret",
        web_host="127.0.0.1",
        web_port=5000,
        tracker_store=str(tmp_path / "experiments"),
        version=__version__,
    )
    monkeypatch.setattr(workspace, "read_record", lambda: record if recorded else None)
    monkeypatch.setattr(workspace, "lock_held", lambda: held)
    monkeypatch.setattr(client, "is_alive", lambda _record: alive)
    monkeypatch.setattr(harnesses.HarnessService, "owned_entries", lambda _self: [])

    report = diagnostics.report(root)

    assert report["handshake"]["status"] == status
    assert report["lock"] == ("held" if held else "free")


def test_doctor_reports_a_network_state_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    monkeypatch.setattr(workspace, "state_dir_is_local", lambda _path=None: False)
    monkeypatch.setattr(workspace, "lock_held", lambda: False)
    monkeypatch.setattr(harnesses.HarnessService, "owned_entries", lambda _self: [])

    report = diagnostics.report(root)

    assert report["state_directory"]["local"] is False
    assert any("file locks are unreliable" in warning for warning in report["warnings"])


def test_daemon_log_keeps_only_the_fixed_number_of_rotated_files() -> None:
    stale = workspace.log_path().with_name(f"{workspace.LOG_NAME}.99")
    stale.parent.mkdir(parents=True)
    stale.write_text("old log", encoding="utf-8")
    daemon_log.configure()
    logger = logging.getLogger("lumlflow.tests.rotation")
    chunk = "x" * (daemon_log.LOG_MAX_BYTES // 2)
    try:
        for index in range(daemon_log.LOG_FILE_COUNT * 3):
            logger.error("rotation %s %s", index, chunk)
    finally:
        daemon_log.close()

    files = sorted(workspace.log_path().parent.glob(f"{workspace.LOG_NAME}*"))
    assert 1 < len(files) <= daemon_log.LOG_FILE_COUNT
    assert workspace.log_path() in files
    assert not stale.exists()


def test_daemon_log_keeps_web_server_tracebacks_out_of_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    daemon_log.configure()
    try:
        try:
            raise RuntimeError("the ASGI server failed")
        except RuntimeError:
            logging.getLogger("uvicorn.error").exception("web server failure")
    finally:
        daemon_log.close()

    captured = capsys.readouterr()
    assert captured.err == ""
    logged = workspace.log_path().read_text("utf-8")
    assert "Traceback" in logged
    assert "RuntimeError: the ASGI server failed" in logged
