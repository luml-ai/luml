"""The connect prompt: the one payload a workspace hands an agent it has never met.

Everything it claims is checkable, and checked here: the flow it names, the
command it tells a harness to spawn, the arguments that command takes, and the
files it sends the reader to. A prompt whose snippet does not start is worse
than none — the reader concludes pairing is broken, not that a path was wrong.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import connect

from tests.daemon.helpers import (
    SCORE_CELL,
    daemon_api,
    make_workspace,
    no_git_words,
    write_cell,
)

_HASH = re.compile(r"\b[0-9a-f]{16,}\b")
_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")


def _fits(line: str) -> bool:
    """Within the column, or over it because one token could not be broken —
    which is what a path is, and breaking one is how a paste goes wrong."""
    longest = max(line.split(), key=len, default="")
    return len(line) <= connect._WIDTH or len(line) - len(longest) < connect._WIDTH


def _config(text: str) -> dict[str, Any]:
    """The JSON block, parsed the way the harness that is handed it will."""
    block = text.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(block)


async def test_the_prompt_names_the_flow_the_workspace_and_the_branch(tmp_path: Path):
    """The role brief is one sentence, and every address in it is one a person
    can read out loud: no ids, no hashes, no version numbers."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        prompt = await api.agent_connect({"flow": "churn"})

    text = str(prompt["text"])
    opening = " ".join(text.split("\n\n", 1)[0].splitlines())

    assert (prompt["flow"], prompt["workspace"]) == ("churn", str(root))
    assert "`churn`" in opening and str(root) in opening and "`main`" in opening
    assert not _HASH.search(text) and not _ULID.search(text)


async def test_the_snippet_registers_a_stdio_server_any_harness_can_spawn(
    tmp_path: Path,
):
    """The hookup is the `mcpServers` object every MCP client reads, naming a
    command that exists and the workspace it is to serve — not a bare
    `lumlflow` that answers to nothing outside the install's own venv."""
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        prompt = await api.agent_connect({"flow": "churn"})

    config = _config(str(prompt["text"]))
    server = config["mcpServers"][connect.SERVER_NAME]

    assert list(config) == ["mcpServers"]
    assert server["command"] == prompt["command"]
    assert Path(server["command"]).exists()
    assert server["args"] == ["mcp", "--workspace", str(root)]


async def test_the_prompt_says_how_to_be_called_something_else(tmp_path: Path):
    """Attribution is the whole point of connecting, so the prompt says where
    the label comes from and how to override it — once, in one sentence."""
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        prompt = await api.agent_connect({"flow": "churn"})

    text = str(prompt["text"])

    assert "--label" in text
    assert text.count("--label") == 1


async def test_a_checked_out_flow_sends_the_agent_to_its_files(tmp_path: Path):
    """The standing rules differ by whether there are files at all: an agent
    told to edit `cells/` in a store-only flow writes where nothing reads."""
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        await api.flow_init({"name": "sales"})
        bound = str((await api.agent_connect({"flow": "churn"}))["text"])
        unbound = str((await api.agent_connect({"flow": "sales"}))["text"])

    assert "`churn.flow/cells/`" in bound
    assert "CHECKOUT.md" in bound
    assert "no files on disk" in unbound
    assert "sales.flow/cells/" not in unbound


async def test_the_prompt_carries_the_rules_an_agent_gets_wrong_on_waking(
    tmp_path: Path,
):
    """Read first, run through the tools, never `input()`, always say why."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        text = str((await api.agent_connect({"flow": "churn"}))["text"])

    assert "`context`" in text
    assert str(root / "AGENTS.md") in text
    assert "`run`" in text
    assert "`input()` fails immediately" in text
    assert "`intent`" in text


async def test_the_prompt_is_short_enough_to_be_read_and_wrapped_to_be_pasted(
    tmp_path: Path,
):
    """Budgeted like `context`: an agent that has to page through its own
    briefing reads none of it, and a user pasting it reads it first.

    Hard-wrapped, too. The same text is read in a popover, a chat box and a
    terminal, and only a paragraph carrying its own line breaks looks the same
    in all three — but never through a path, which is pasted rather than read.
    """
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        text = str((await api.agent_connect({"flow": "churn"}))["text"])

    lines = text.splitlines()
    before, _, rest = text.partition("```json")
    prose = [*before.splitlines(), *rest.partition("```")[2].splitlines()]

    assert len(lines) <= 50
    assert all(_fits(line) for line in prose)
    # Wrapped at whitespace only: every path in it survives being pasted.
    assert str(root / "AGENTS.md") in text


def test_the_command_the_snippet_names_serves_mcp(tmp_path: Path):
    """The cross-check the prompt exists to survive: the exact command line it
    prints is run, from a directory that is not the workspace, and answers."""
    root = make_workspace(tmp_path / "project")
    command = connect.executable()
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
        [command, "mcp", "--workspace", str(root)],
        input=json.dumps(handshake) + "\n",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=60,
    )
    hello = json.loads(answered.stdout.splitlines()[0])

    assert hello["result"]["serverInfo"]["name"] == "lumlflow"
    assert hello["result"]["capabilities"] == {"tools": {}, "resources": {}}


async def test_the_prompt_never_speaks_the_vocabulary_git_owns(tmp_path: Path):
    """An agent reads this inside somebody's git repository. It must not blur."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        bound = await api.agent_connect({"flow": "churn"})
        await api.flow_init({"name": "sales"})
        unbound = await api.agent_connect({"flow": "sales"})

    no_git_words(str(bound["text"]), "the connect prompt with files")
    no_git_words(str(unbound["text"]), "the connect prompt without files")
