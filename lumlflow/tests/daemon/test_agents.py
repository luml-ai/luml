import json
import stat
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import harnesses
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.main import Daemon

from tests.daemon.helpers import make_workspace


def _executable(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _service(
    tmp_path: Path,
    *,
    binaries: tuple[str, ...] = ("claude", "lumlflow"),
    running_executable: str | None = None,
) -> harnesses.HarnessService:
    binary_dir = tmp_path / "bin"
    for binary in binaries:
        _executable(binary_dir / binary)
    return harnesses.HarnessService(
        running_executable=running_executable or binary_dir / "lumlflow",
        state_directory=tmp_path / "state",
        home=tmp_path / "home",
        platform="linux",
        environment={"PATH": str(binary_dir)},
    )


def _one(result: dict[str, Any]) -> dict[str, Any]:
    return result["harnesses"][0]


@pytest.mark.asyncio
async def test_agents_api_records_consent_and_remove_clears_it(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "workspace", flows=())
    service = _service(tmp_path)
    config = tmp_path / "home" / ".claude.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    before_decline = config.read_bytes()
    hub = Hub()
    api = Api(hub, directory=root, harness_service=service)

    try:
        initial = _one(await api.methods["agents.harnesses"]({}))
        declined = await api.methods["agents.setup"](
            {"harness": "claude-code", "consent": False}
        )

        assert initial["state"] == "not set up"
        assert initial["consent_required"]
        assert declined["state"] == "not set up"
        assert config.read_bytes() == before_decline
        assert not service.consent_path.exists()

        set_up = await api.methods["agents.setup"](
            {"harness": "claude-code", "consent": True}
        )
        document = json.loads(config.read_text("utf-8"))

        assert set_up["state"] == "set up"
        assert set_up["post_write_hint"] == ("approve the server when Claude Code asks")
        assert document["theme"] == "dark"
        assert document["mcpServers"]["lumlflow"]["args"] == ["mcp"]
        assert service.has_consent("claude-code")

        document["mcpServers"]["lumlflow-old"] = {
            "command": "/old/bin/lumlflow",
            "env": {harnesses.MANAGED_ENV: "0.0.1"},
        }
        document["mcpServers"]["foreign"] = {"command": "node"}
        config.write_text(json.dumps(document), encoding="utf-8")

        removed = await api.methods["agents.remove"]({"harness": "claude-code"})
        after_remove = json.loads(config.read_text("utf-8"))

        assert removed["state"] == "not set up"
        assert removed["consent_required"]
        assert after_remove == {
            "theme": "dark",
            "mcpServers": {"foreign": {"command": "node"}},
        }
        assert not service.has_consent("claude-code")
    finally:
        await hub.close()


def test_sync_rewrites_a_path_scoped_entry_but_honours_manual_removal(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.setup("claude-code", consent=True)
    config = tmp_path / "home" / ".claude.json"
    document = json.loads(config.read_text("utf-8"))
    document["mcpServers"]["lumlflow"] = {
        "command": "/old/bin/lumlflow",
        "args": ["mcp", "--workspace", "/old/project"],
        "env": {harnesses.MANAGED_ENV: "0.0.1"},
    }
    config.write_text(json.dumps(document), encoding="utf-8")

    synced = service.list_harnesses()
    entry = json.loads(config.read_text("utf-8"))["mcpServers"]["lumlflow"]

    assert synced[0]["state"] == "set up"
    assert entry["command"] == "lumlflow"
    assert entry["args"] == ["mcp"]

    config.unlink()
    removed = service.list_harnesses()[0]

    assert removed["state"] == "removed by you"
    assert not config.exists()


def test_failed_sync_is_the_only_time_an_owned_entry_stays_out_of_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    service.setup("claude-code", consent=True)
    config = tmp_path / "home" / ".claude.json"
    document = json.loads(config.read_text("utf-8"))
    document["mcpServers"]["lumlflow"]["env"][harnesses.MANAGED_ENV] = "0.0.1"
    config.write_text(json.dumps(document), encoding="utf-8")
    atomic_write = harnesses.atomic_write_bytes

    def refuse_config(path: Path, data: bytes) -> None:
        if path == config:
            raise PermissionError("read only")
        atomic_write(path, data)

    monkeypatch.setattr(harnesses, "atomic_write_bytes", refuse_config)

    listed = service.list_harnesses()[0]

    assert listed["state"] == "out of date"
    assert listed["action"] == "update"
    assert "read only" in listed["error"]


def test_unparseable_sync_is_left_untouched_and_stays_out_of_date(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.setup("claude-code", consent=True)
    config = tmp_path / "home" / ".claude.json"
    original = b"{ no longer valid json"
    config.write_bytes(original)

    listed = service.list_harnesses()[0]

    assert listed["state"] == "out of date"
    assert listed["action"] == "update"
    assert listed["config_path"] == str(config)
    assert "mcpServers" in listed["snippet"]
    assert "does not parse" in listed["error"]
    assert config.read_bytes() == original


def test_unparseable_first_setup_is_left_unmodified_and_unconsented(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    config = tmp_path / "home" / ".claude.json"
    config.parent.mkdir()
    original = b"{ not json"
    config.write_bytes(original)

    result = service.setup("claude-code", consent=True)

    assert result["state"] == "not set up"
    assert result["action"] == "setup"
    assert result["config_path"] == str(config)
    assert "mcpServers" in result["snippet"]
    assert "does not parse" in result["error"]
    assert config.read_bytes() == original
    assert not service.has_consent("claude-code")


def test_api_reports_a_current_entry_with_a_missing_command_as_broken(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing" / "lumlflow"
    service = _service(
        tmp_path,
        binaries=("claude",),
        running_executable=str(missing),
    )
    harness = harnesses.harness_by_id("claude-code")
    config = tmp_path / "home" / ".claude.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "lumlflow": harnesses.desired_entry(
                        harness, executable=str(missing)
                    )
                }
            }
        ),
        encoding="utf-8",
    )

    listed = service.list_harnesses()[0]

    assert listed["state"] == "broken"
    assert listed["action"] is None


def test_detect_only_harness_is_listed_with_no_setup_action(tmp_path: Path) -> None:
    service = _service(tmp_path, binaries=("idea", "lumlflow"))

    (listed,) = service.list_harnesses()

    assert listed["id"] == "jetbrains-ai"
    assert listed["state"] == "not set up"
    assert listed["config_path"] == (
        "Settings > Tools > AI Assistant > Model Context Protocol (MCP)"
    )
    assert "mcpServers" in listed["snippet"]
    assert not listed["can_setup"]
    assert listed["action"] is None


def test_setup_and_sync_never_write_under_the_workspace(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "workspace", flows=("churn",))
    service = _service(tmp_path)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    service.setup("claude-code", consent=True)
    service.list_harnesses()

    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.asyncio
async def test_daemon_start_runs_the_agent_sync_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daemon = Daemon(tmp_path)
    calls = 0

    def sync_agents() -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(daemon.api, "sync_agents", sync_agents)
    monkeypatch.setattr(daemon.watcher, "start", lambda: None)
    monkeypatch.setattr(daemon, "_serve_web", lambda listener: listener.close())

    await daemon.serve(web_port=0, announce=lambda _record: daemon.stop())

    assert calls == 1
