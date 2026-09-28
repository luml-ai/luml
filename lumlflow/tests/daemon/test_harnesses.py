import json
import os
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import harnesses

from tests.daemon.helpers import make_workspace


def _executable(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _fixture(shape: harnesses.ConfigShape) -> str:
    if shape == harnesses.ConfigShape.TOML:
        return '[theme]\nname = "dark"\n\n[mcp_servers.foreign]\ncommand = "node"\n'
    return json.dumps(
        {
            "theme": "dark",
            shape.value: {"foreign": {"command": "node", "args": ["server.js"]}},
        }
    )


def _read(path: Path, shape: harnesses.ConfigShape) -> dict[str, Any]:
    if shape == harnesses.ConfigShape.TOML:
        return tomllib.loads(path.read_text("utf-8"))
    return json.loads(path.read_text("utf-8"))


@pytest.mark.parametrize(
    "harness",
    [entry for entry in harnesses.HARNESSES if entry.writer is not None],
    ids=lambda entry: entry.id,
)
def test_each_verified_harness_round_trips_without_losing_foreign_entries(
    tmp_path: Path, harness: harnesses.Harness
) -> None:
    assert harness.shape is not None
    path = (
        tmp_path
        / harness.id
        / (
            "config.toml"
            if harness.shape == harnesses.ConfigShape.TOML
            else "config.json"
        )
    )
    path.parent.mkdir(parents=True)
    original = _fixture(harness.shape)
    path.write_text(original, encoding="utf-8")
    executable = _executable(tmp_path / "bin" / "lumlflow")

    result = harnesses.write_config(harness, executable=executable, path=path)

    document = _read(path, harness.shape)
    section_key = (
        "mcp_servers"
        if harness.shape == harnesses.ConfigShape.TOML
        else harness.shape.value
    )
    assert result.changed
    expected_theme: object = (
        {"name": "dark"} if harness.shape == harnesses.ConfigShape.TOML else "dark"
    )
    assert document["theme"] == expected_theme
    assert document[section_key]["foreign"]["command"] == "node"
    assert document[section_key][harnesses.SERVER_NAME] == harnesses.desired_entry(
        harness, executable=executable
    )
    assert path.with_name(f"{path.name}.bak").read_text("utf-8") == original
    assert (
        harnesses.entry_state(harness, executable=executable, path=path)
        == harnesses.EntryState.SET_UP
    )


@pytest.mark.parametrize("harness_id", ["cursor", "codex", "opencode"])
def test_unparseable_configs_are_refused_without_a_backup(
    tmp_path: Path, harness_id: str
) -> None:
    harness = harnesses.harness_by_id(harness_id)
    suffix = ".toml" if harness.shape == harnesses.ConfigShape.TOML else ".json"
    path = tmp_path / f"broken{suffix}"
    original = b"this does not parse [[["
    path.write_bytes(original)

    with pytest.raises(harnesses.HarnessConfigError, match="does not parse"):
        harnesses.write_config(harness, executable="lumlflow", path=path)

    assert path.read_bytes() == original
    assert not path.with_name(f"{path.name}.bak").exists()


def test_an_unchanged_entry_does_not_touch_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = harnesses.harness_by_id("claude-code")
    path = tmp_path / ".claude.json"
    harnesses.write_config(harness, executable="lumlflow", path=path)
    original = path.read_bytes()

    def fail_write(_path: Path, _data: bytes) -> None:
        raise AssertionError("unchanged config was written")

    monkeypatch.setattr(harnesses, "atomic_write_bytes", fail_write)
    result = harnesses.write_config(harness, executable="lumlflow", path=path)

    assert not result.changed
    assert path.read_bytes() == original


def test_a_missing_codex_directory_and_file_are_created_without_a_backup(
    tmp_path: Path,
) -> None:
    harness = harnesses.harness_by_id("codex")
    user_home = tmp_path / "home"
    expected = user_home / ".codex" / "config.toml"

    result = harnesses.write_config(
        harness,
        executable="lumlflow",
        home=user_home,
        platform="linux",
        environment={},
    )

    assert result.path == expected
    assert tomllib.loads(expected.read_text("utf-8"))["mcp_servers"]["lumlflow"][
        "args"
    ] == ["mcp"]
    assert not expected.with_name("config.toml.bak").exists()


def test_owned_entries_lists_only_configs_lumlflow_manages(tmp_path: Path) -> None:
    user_home = tmp_path / "home"
    executable = _executable(tmp_path / "bin" / "lumlflow")
    codex = harnesses.harness_by_id("codex")
    harnesses.write_config(
        codex,
        executable=executable,
        home=user_home,
        platform="linux",
        environment={},
    )
    service = harnesses.HarnessService(
        executable,
        home=user_home,
        platform="linux",
        environment={},
        search_path="",
    )

    owned = service.owned_entries()

    assert [(entry["id"], entry["state"]) for entry in owned] == [("codex", "set up")]


def test_first_touch_backup_is_not_replaced_on_later_updates(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("gemini")
    path = tmp_path / "settings.json"
    original = b'{"theme": "dark"}\n'
    path.write_bytes(original)

    harnesses.write_config(harness, executable="lumlflow", version="0.1.0", path=path)
    harnesses.write_config(harness, executable="lumlflow", version="0.2.0", path=path)

    assert path.with_name("settings.json.bak").read_bytes() == original
    entry = json.loads(path.read_text("utf-8"))["mcpServers"]["lumlflow"]
    assert entry["env"][harnesses.MANAGED_ENV] == "0.2.0"


def test_owned_legacy_names_are_replaced_but_unmanaged_names_are_preserved(
    tmp_path: Path,
) -> None:
    harness = harnesses.harness_by_id("cursor")
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "lumlflow-old": {
                        "command": "/old/lumlflow",
                        "args": ["mcp", "--workspace", "/old/project"],
                        "env": {harnesses.MANAGED_ENV: "0.0.1"},
                    },
                    "foreign": {"command": "node"},
                }
            }
        ),
        encoding="utf-8",
    )

    harnesses.write_config(harness, executable="lumlflow", path=path)

    servers = json.loads(path.read_text("utf-8"))["mcpServers"]
    assert set(servers) == {"foreign", "lumlflow"}
    assert servers["lumlflow"]["args"] == ["mcp"]


def test_an_unmarked_prerelease_lumlflow_entry_is_replaced(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("cursor")
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "lumlflow": {
                        "command": "/old/bin/lumlflow",
                        "args": ["mcp", "--workspace", "/old/project"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    harnesses.write_config(harness, executable="lumlflow", path=path)

    entry = json.loads(path.read_text("utf-8"))["mcpServers"]["lumlflow"]
    assert entry == harnesses.desired_entry(harness, executable="lumlflow")


def test_desktop_setup_is_one_static_entry_for_every_flow(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("claude-desktop")
    path = tmp_path / "claude_desktop_config.json"

    first = harnesses.write_config(harness, executable="lumlflow", path=path)
    second = harnesses.write_config(harness, executable="lumlflow", path=path)

    assert first.changed and not second.changed
    servers = json.loads(path.read_text("utf-8"))["mcpServers"]
    assert list(servers) == ["lumlflow"]
    assert servers["lumlflow"]["args"] == ["mcp"]
    assert all("workspace" not in arg for arg in servers["lumlflow"]["args"])


def test_out_of_date_and_broken_entries_are_distinct(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("claude-code")
    path = tmp_path / ".claude.json"
    old_executable = _executable(tmp_path / "old-bin" / "lumlflow")
    current_executable = _executable(tmp_path / "current-bin" / "lumlflow")
    old_entry = harnesses.desired_entry(
        harness, executable=old_executable, version="0.0.1"
    )
    path.write_text(json.dumps({"mcpServers": {"lumlflow": old_entry}}), "utf-8")

    assert (
        harnesses.entry_state(
            harness, executable=current_executable, version="0.1.0", path=path
        )
        == harnesses.EntryState.OUT_OF_DATE
    )

    Path(old_executable).unlink()
    assert (
        harnesses.entry_state(
            harness, executable=current_executable, version="0.1.0", path=path
        )
        == harnesses.EntryState.OUT_OF_DATE
    )

    harnesses.write_config(
        harness, executable=current_executable, version="0.1.0", path=path
    )
    Path(current_executable).unlink()
    assert (
        harnesses.entry_state(
            harness, executable=current_executable, version="0.1.0", path=path
        )
        == harnesses.EntryState.BROKEN
    )


def test_a_detect_only_harness_has_a_snippet_but_no_writer(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("jetbrains-ai")

    assert harness.writer is None
    assert "mcpServers" in harnesses.config_snippet(harness, executable="lumlflow")
    with pytest.raises(harnesses.HarnessConfigError, match="detect-only"):
        harnesses.write_config(
            harness, executable="lumlflow", path=tmp_path / "config.json"
        )


def test_detection_uses_binaries_or_user_config_directories(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    _executable(binary_dir / "gemini")
    user_home = tmp_path / "home"
    (user_home / ".cursor").mkdir(parents=True)

    detected = harnesses.detected_harnesses(
        home=user_home,
        platform="linux",
        environment={"PATH": str(binary_dir)},
    )

    assert {entry.id for entry in detected} == {"cursor", "gemini"}


def test_executable_is_bare_on_path_and_absolute_otherwise(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    on_path = _executable(binary_dir / "lumlflow")
    running = tmp_path / "venv" / "bin" / "lumlflow"

    assert (
        harnesses.resolve_executable(running, search_path=str(binary_dir)) == "lumlflow"
    )
    assert harnesses.resolve_executable(running, search_path="") == str(
        running.resolve()
    )
    assert Path(on_path).is_file()


def test_registry_records_only_verified_shell_markers() -> None:
    markers = {
        entry.id: entry.environment_marker
        for entry in harnesses.HARNESSES
        if entry.shell
    }

    assert markers == {
        "claude-code": "CLAUDECODE",
        "cursor": "CURSOR_AGENT",
        "codex": None,
        "gemini": "GEMINI_CLI",
        "opencode": None,
        "copilot": None,
    }
    assert all(
        entry.environment_marker is None
        for entry in harnesses.HARNESSES
        if not entry.shell
    )
    assert all(entry.verification for entry in harnesses.HARNESSES)


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({"CLAUDECODE": "1"}, "claude-code"),
        ({"CURSOR_AGENT": ""}, "cursor"),
        ({"GEMINI_CLI": "true"}, "gemini"),
        ({"CODEX_SHELL": "1"}, "user"),
        ({}, "user"),
    ],
)
def test_shell_actor_uses_only_verified_environment_markers(
    environment: dict[str, str], expected: str
) -> None:
    assert harnesses.shell_actor(environment) == expected


def test_lumlflow_actor_precedes_a_harness_environment_marker() -> None:
    assert (
        harnesses.shell_actor({"LUMLFLOW_ACTOR": "pair-1", "CLAUDECODE": "1"})
        == "pair-1"
    )


def test_registry_records_verified_cwd_behavior_and_agent_classes() -> None:
    cwd_behavior = {entry.id: entry.cwd_is_project for entry in harnesses.HARNESSES}
    shell_harnesses = {entry.id for entry in harnesses.HARNESSES if entry.shell}

    assert cwd_behavior == {
        "claude-code": True,
        "claude-desktop": False,
        "cursor": True,
        "windsurf": True,
        "vscode": True,
        "codex": True,
        "gemini": True,
        "opencode": True,
        "copilot": True,
        "jetbrains-ai": None,
    }
    assert shell_harnesses == {
        "claude-code",
        "cursor",
        "codex",
        "gemini",
        "opencode",
        "copilot",
    }


def test_resolved_platform_paths_are_user_level(tmp_path: Path) -> None:
    environment = {"APPDATA": str(tmp_path / "Roaming")}

    linux_paths = {
        entry.id: entry.config_path(home=tmp_path, platform="linux", environment={})
        for entry in harnesses.HARNESSES
    }
    assert linux_paths == {
        "claude-code": tmp_path / ".claude.json",
        "claude-desktop": None,
        "cursor": tmp_path / ".cursor" / "mcp.json",
        "windsurf": tmp_path / ".codeium" / "windsurf" / "mcp_config.json",
        "vscode": tmp_path / ".config" / "Code" / "User" / "mcp.json",
        "codex": tmp_path / ".codex" / "config.toml",
        "gemini": tmp_path / ".gemini" / "settings.json",
        "opencode": tmp_path / ".config" / "opencode" / "opencode.json",
        "copilot": tmp_path / ".copilot" / "mcp-config.json",
        "jetbrains-ai": None,
    }

    assert (
        harnesses.harness_by_id("vscode").config_path(
            home=tmp_path, platform="win32", environment=environment
        )
        == tmp_path / "Roaming" / "Code" / "User" / "mcp.json"
    )
    assert harnesses.harness_by_id("claude-desktop").config_path(
        home=tmp_path, platform="darwin", environment={}
    ) == (
        tmp_path
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )
    assert (
        harnesses.harness_by_id("codex").config_path(
            home=tmp_path,
            platform="linux",
            environment={"CODEX_HOME": str(tmp_path / "custom-codex")},
        )
        == tmp_path / "custom-codex" / "config.toml"
    )
    assert os.sep not in harnesses.SERVER_NAME


def test_entries_use_the_verified_json_and_toml_shapes() -> None:
    version = "1.2.3"
    common = {
        "command": "lumlflow",
        "args": ["mcp"],
        "env": {harnesses.MANAGED_ENV: version},
    }

    for harness_id in (
        "claude-code",
        "claude-desktop",
        "cursor",
        "windsurf",
        "codex",
        "gemini",
    ):
        assert (
            harnesses.desired_entry(
                harnesses.harness_by_id(harness_id),
                executable="lumlflow",
                version=version,
            )
            == common
        )

    assert harnesses.desired_entry(
        harnesses.harness_by_id("vscode"),
        executable="lumlflow",
        version=version,
    ) == {"type": "stdio", **common}
    assert harnesses.desired_entry(
        harnesses.harness_by_id("opencode"),
        executable="lumlflow",
        version=version,
    ) == {
        "type": "local",
        "command": ["lumlflow", "mcp"],
        "environment": {harnesses.MANAGED_ENV: version},
    }
    assert harnesses.desired_entry(
        harnesses.harness_by_id("copilot"),
        executable="lumlflow",
        version=version,
    ) == {"type": "local", **common, "tools": ["*"]}


def test_opencode_jsonc_is_updated_without_losing_foreign_keys(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("opencode")
    path = tmp_path / "opencode.json"
    path.write_text(
        """{
  "$schema": "https://opencode.ai/config.json",
  // OpenCode accepts comments and trailing commas in this file.
  "theme": "dark",
  "mcp": {
    "foreign": {"type": "local", "command": ["node", "server.js"],},
  },
}
""",
        encoding="utf-8",
    )

    harnesses.write_config(harness, executable="lumlflow", path=path)

    document = json.loads(path.read_text("utf-8"))
    assert document["theme"] == "dark"
    assert document["mcp"]["foreign"]["command"] == ["node", "server.js"]
    assert document["mcp"]["lumlflow"]["command"] == ["lumlflow", "mcp"]


def test_vscode_jsonc_is_updated_without_losing_foreign_keys(tmp_path: Path) -> None:
    harness = harnesses.harness_by_id("vscode")
    path = tmp_path / "mcp.json"
    path.write_text(
        """{
  // VS Code parses mcp.json as JSON with comments.
  "servers": {
    "foreign": {"type": "stdio", "command": "node",},
  },
}
""",
        encoding="utf-8",
    )

    harnesses.write_config(harness, executable="lumlflow", path=path)

    servers = json.loads(path.read_text("utf-8"))["servers"]
    assert servers["foreign"] == {"type": "stdio", "command": "node"}
    assert servers["lumlflow"]["type"] == "stdio"


def test_an_unmanaged_lumlflow_name_is_refused_without_touching_the_file(
    tmp_path: Path,
) -> None:
    harness = harnesses.harness_by_id("claude-code")
    path = tmp_path / ".claude.json"
    original = json.dumps({"mcpServers": {"lumlflow": {"command": "unrelated-server"}}})
    path.write_text(original, encoding="utf-8")

    with pytest.raises(harnesses.HarnessConfigError, match="unmanaged server"):
        harnesses.write_config(harness, executable="lumlflow", path=path)

    assert path.read_text("utf-8") == original
    assert not path.with_name(".claude.json.bak").exists()


def test_writer_rereads_after_creating_the_first_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = harnesses.harness_by_id("claude-code")
    path = tmp_path / ".claude.json"
    path.write_text(
        json.dumps({"mcpServers": {"foreign": {"command": "node"}}}),
        encoding="utf-8",
    )
    backup = path.with_name(".claude.json.bak")
    atomic_write = harnesses.atomic_write_bytes

    def race_after_backup(target: Path, data: bytes) -> None:
        atomic_write(target, data)
        if target == backup:
            document = json.loads(path.read_text("utf-8"))
            document["late-key"] = "kept"
            path.write_text(json.dumps(document), encoding="utf-8")

    monkeypatch.setattr(harnesses, "atomic_write_bytes", race_after_backup)

    harnesses.write_config(harness, executable="lumlflow", path=path)

    document = json.loads(path.read_text("utf-8"))
    assert document["late-key"] == "kept"
    assert document["mcpServers"]["foreign"] == {"command": "node"}
    assert document["mcpServers"]["lumlflow"]["args"] == ["mcp"]


def test_the_harness_entry_command_serves_mcp_without_a_workspace_argument(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    installed = Path(sys.executable).with_name("lumlflow")
    command = harnesses.resolve_executable(installed, search_path="")
    if not Path(command).exists():
        pytest.skip("lumlflow is not installed as a console script here")
    handshake = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "1.0"},
        },
    }

    answered = subprocess.run(
        [command, "mcp"],
        input=json.dumps(handshake) + "\n",
        capture_output=True,
        text=True,
        cwd=root,
        timeout=60,
    )
    hello = json.loads(answered.stdout.splitlines()[0])

    assert hello["result"]["serverInfo"]["name"] == "lumlflow"
    assert hello["result"]["capabilities"] == {"tools": {}, "resources": {}}
