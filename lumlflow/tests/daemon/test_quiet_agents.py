"""A connected agent that stops calling stops counting as here.

A harness can keep its MCP server — and with it the connection — alive long
after the session that started it ended. So presence is the connection *and*
a call within `QUIET_AFTER_S`: past that the session is ended as if the agent
had hung up, and its next call brings it back under the same lease.
"""

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon.main import QUIET_AFTER_S, Daemon

from tests.daemon.helpers import make_workspace


class _Clock:
    def __init__(self) -> None:
        self.now = 10_000.0

    def __call__(self) -> float:
        return self.now


class _Agent:
    """One connection to the daemon, speaking its line protocol."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.next_id = 0

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        self.next_id += 1
        asked = self.next_id
        line = {"jsonrpc": "2.0", "id": asked, "method": method, "params": params}
        self.writer.write(json.dumps(line).encode() + b"\n")
        await self.writer.drain()
        while True:
            answer = json.loads(await asyncio.wait_for(self.reader.readline(), 10))
            if answer.get("id") == asked:
                if "error" in answer:
                    raise AssertionError(answer["error"])
                return answer["result"]


@contextlib.asynccontextmanager
async def _daemon(root: Path, monkeypatch: pytest.MonkeyPatch):
    daemon = Daemon(root)
    clock = _Clock()
    daemon.clock = clock
    ready = asyncio.Event()
    monkeypatch.setattr(daemon.api, "sync_agents", lambda: [])
    monkeypatch.setattr(daemon.watcher, "start", lambda: None)
    monkeypatch.setattr(daemon, "_serve_web", lambda listener: listener.close())
    serving = asyncio.create_task(
        daemon.serve(web_port=0, announce=lambda _record: ready.set())
    )
    await asyncio.wait_for(ready.wait(), 30)
    try:
        yield daemon, clock
    finally:
        daemon.stop()
        await asyncio.wait_for(serving, 30)


async def _connect(daemon: Daemon) -> _Agent:
    reader, writer = await asyncio.open_connection("127.0.0.1", daemon.port)
    writer.write(
        json.dumps(
            {"method": "authenticate", "params": {"token": daemon.token}}
        ).encode()
        + b"\n"
    )
    await writer.drain()
    return _Agent(reader, writer)


async def _present(daemon: Daemon) -> dict[str, tuple[str, bool]]:
    tree = await daemon.api.tree({"flow": "churn"})
    return {
        row["actor"]: (row["label"], row["leased"]) for row in tree["agent_sessions"]
    }


async def test_a_quiet_agent_leaves_and_its_next_call_brings_it_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    async with _daemon(root, monkeypatch) as (daemon, clock):
        codex = await _connect(daemon)
        claude = await _connect(daemon)
        try:
            await codex.call("flow.open", {"flow": "churn"})
            for agent, actor, label in (
                (codex, "codex-1", "codex"),
                (claude, "claude-1", "claude-code"),
            ):
                await agent.call(
                    "agent.begin",
                    {"flow": "churn", "actor": actor, "label": label, "lease": True},
                )
            both = await _present(daemon)

            clock.now += QUIET_AFTER_S - 60
            await claude.call("context", {"flow": "churn", "actor": "claude-1"})
            clock.now += 60
            await daemon.end_quiet()
            after_quiet = await _present(daemon)

            await codex.call("context", {"flow": "churn", "actor": "codex-1"})
            back = await _present(daemon)
        finally:
            for agent in (codex, claude):
                agent.writer.close()

    assert both == {"codex-1": ("codex", True), "claude-1": ("claude-code", True)}
    # Codex made no call for the whole window and is gone; Claude called
    # within it and stays.
    assert after_quiet == {"claude-1": ("claude-code", True)}
    assert back == {"codex-1": ("codex", True), "claude-1": ("claude-code", True)}


async def test_a_quiet_agent_gives_its_name_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new window of the same harness is not numbered after a gone one."""
    root = make_workspace(tmp_path / "project")
    async with _daemon(root, monkeypatch) as (daemon, clock):
        stale = await _connect(daemon)
        fresh = await _connect(daemon)
        try:
            await stale.call("flow.open", {"flow": "churn"})
            await stale.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex-1", "label": "codex", "lease": True},
            )
            clock.now += QUIET_AFTER_S
            await daemon.end_quiet()
            begun = await fresh.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex-2", "label": "codex", "lease": True},
            )
            # The stale one comes back and takes the next free name.
            await stale.call("context", {"flow": "churn", "actor": "codex-1"})
            present = await _present(daemon)
        finally:
            for agent in (stale, fresh):
                agent.writer.close()

    assert begun["label"] == "codex"
    assert present == {"codex-2": ("codex", True), "codex-1": ("codex 2", True)}


async def test_a_ping_is_not_presence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    async with _daemon(root, monkeypatch) as (daemon, clock):
        codex = await _connect(daemon)
        try:
            await codex.call("flow.open", {"flow": "churn"})
            await codex.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex-1", "label": "codex", "lease": True},
            )
            clock.now += QUIET_AFTER_S - 1
            await codex.call("ping", {"actor": "codex-1"})
            clock.now += 1
            await daemon.end_quiet()
            present = await _present(daemon)
        finally:
            codex.writer.close()

    assert present == {}
