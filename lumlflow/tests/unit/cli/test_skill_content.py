"""Keep the Flow skill true to the installed lumlflow.

Every `lumlflow ...` command the skill names must resolve to a real command, the
agent ids must match the harness table, and the skill's flow guide must be the
text `lumlflow guide` serves.
"""

import re
from pathlib import Path
from typing import Any

import typer
from lumlflow.cli import app
from lumlflow.flow.daemon import docs
from lumlflow.flow.daemon.harnesses import HARNESSES

SKILL_DIR = Path(__file__).resolve().parents[3] / "lumlflow/skills/lumlflow"
COMMAND = re.compile(r"(?:`|^)lumlflow((?: [a-z][a-z-]*)+)", re.MULTILINE)
ROOT = typer.main.get_command(app)


def _skill_text() -> str:
    return "\n".join(path.read_text() for path in sorted(SKILL_DIR.rglob("*.md")))


def _resolves(command: Any, words: list[str]) -> bool:
    """Follow the words down the command tree; leftover words are arguments."""
    for word in words:
        if not hasattr(command, "get_command"):
            return True
        found = command.get_command(None, word)
        if found is None:
            return command is not ROOT
        command = found
    return True


def test_every_named_command_exists() -> None:
    named = {match.strip() for match in COMMAND.findall(_skill_text())}
    assert "ui" in {words.split()[0] for words in named}
    for words in sorted(named):
        assert _resolves(ROOT, words.split()), f"lumlflow {words}"


def test_agent_ids_match_the_harness_table() -> None:
    agents = (SKILL_DIR / "references/agents.md").read_text()
    (line,) = [line for line in agents.splitlines() if line.startswith("Agent ids:")]
    sentence = agents[agents.index(line) :].split(".")[0]
    listed = set(re.findall(r"`([a-z-]+)`", sentence))
    assert listed == {harness.id for harness in HARNESSES}


def test_the_flow_guide_is_the_served_guide() -> None:
    assert (SKILL_DIR / "references/flows.md").read_text("utf-8") == docs.CHEATSHEET
