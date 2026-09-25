from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import client, envs, harnesses, workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.settings import Settings


def report(directory: Path) -> dict[str, Any]:
    requested = directory.resolve()
    record = workspace.read_record()
    held = workspace.lock_held()
    handshake = _handshake(record, held=held)
    interpreter = envs.describe(requested)
    flows = _flow_store_usage(requested)
    warnings = [
        warning
        for warning in (
            workspace.network_filesystem_warning(),
            _network_bind_warning(record, handshake),
        )
        if warning is not None
    ]
    tracker_store = (
        record.tracker_store
        if record is not None and handshake["status"] == "answering"
        else Settings().BACKEND_STORE_URI  # type: ignore[call-arg]
    )
    return {
        "directory": str(requested),
        "state_directory": {
            "path": str(workspace.state_dir().resolve()),
            "local": workspace.state_dir_is_local(),
        },
        "record": _record(record),
        "lock": "held" if held else "free",
        "handshake": handshake,
        "log_path": str(workspace.log_path().resolve()),
        "interpreter": {
            "path": str(interpreter.python.resolve()),
            "source": interpreter.source,
        },
        "tracker_store": tracker_store,
        "flow_stores": flows,
        "harness_entries": harnesses.HarnessService().owned_entries(),
        "warnings": warnings,
    }


def _record(record: DaemonRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "pid": record.pid,
        "instance_id": record.instance_id,
        "socket_address": f"127.0.0.1:{record.port}",
        "web_host": record.web_host,
        "web_port": record.web_port,
        "tracker_store": record.tracker_store,
        "version": record.version,
    }


def _handshake(record: DaemonRecord | None, *, held: bool) -> dict[str, Any]:
    if record is not None and client.is_alive(record):
        return {"status": "answering", "instance_id": record.instance_id}
    if record is not None and not held:
        return {"status": "stale record", "instance_id": record.instance_id}
    return {
        "status": "not answering",
        "instance_id": record.instance_id if record is not None else None,
    }


def _network_bind_warning(
    record: DaemonRecord | None, handshake: dict[str, Any]
) -> str | None:
    if (
        record is None
        or handshake["status"] != "answering"
        or workspace.is_loopback_host(record.web_host)
    ):
        return None
    return f"warning: {workspace.NON_LOOPBACK_WARNING}"


def _flow_store_usage(directory: Path) -> dict[str, Any]:
    flows: list[dict[str, Any]] = []
    for ref in workspace.find_flows(directory):
        path = store_dir(ref.path)
        if not path.is_dir():
            continue
        flows.append(
            {
                "flow": ref.name,
                "path": str(path),
                "disk_bytes": _directory_bytes(path),
            }
        )
    return {
        "count": len(flows),
        "disk_bytes": sum(int(flow["disk_bytes"]) for flow in flows),
        "flows": flows,
    }


def _directory_bytes(directory: Path) -> int:
    total = 0
    for entry in directory.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total
