"""The connect prompt: what a workspace hands an agent so it can pair itself.

Same philosophy as `handoff.py` — built where the facts are, addresses only,
budgeted — for the one payload that is not about a cell: the wake-up brief an
agent is given before it has ever seen this workspace. The user copies it into
whatever harness they run; the harness connects back over MCP, and from that
connection on, everything it does is attributed without anybody wrapping
anything.

Harness-agnostic by construction. Nothing here names a product: the hookup is
the `mcpServers` object every MCP-capable client reads, plus one sentence for
the ones that take the same two facts through a UI. The command is resolved
against the interpreter serving this workspace rather than spelled `lumlflow`
and hoped for, because a venv install is on nobody's PATH and a snippet that
fails at the first spawn teaches the reader that pairing is broken.
"""

import json
import os
import shutil
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumlflow.flow.daemon.docs import AGENTS_NAME, CHECKOUT_NAME
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, STORE_DIRNAME

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

#: What the server is called in the config it is registered under.
SERVER_NAME = "lumlflow"

#: Hard-wrapped, not left to whoever renders it: this text is read in a popover,
#: in a chat box and in a terminal, and only the paragraphs that carry their own
#: line breaks look the same in all three. Paths are never broken — a path split
#: across two lines is a path somebody pastes wrong.
_WIDTH = 72


def prompt(session: "FlowSession", *, workspace_dir: Path) -> dict[str, Any]:
    """The paste-ready brief that pairs an agent with this flow.

    One block, in the order an agent reads: who it is working with, how to
    connect, what to read, and the rules that hold from then on.
    """
    root = str(workspace_dir)
    lines = [
        *_para(
            f"You are paired with the lumlflow flow `{session.ref.name}` in "
            f"`{root}`, on lane `{session.branch}`. Its cells live there. "
            "So does every version of them, and every result they produced. "
            "Connect to the flow and work through the connection. lumlflow "
            "then records what you do as yours."
        ),
        "",
        "Register lumlflow as an MCP server:",
        "",
        *_snippet(root),
        "",
        *_para(
            "A harness that configures MCP servers through its own UI or "
            "command takes the same two facts: the command above, and those "
            "arguments. Your harness sends its own name in the handshake. "
            "That name becomes the label this flow attributes your work to. "
            "Add `--label <name>` to the arguments to be called something "
            "else."
        ),
        "",
        "Then, before anything else:",
        "",
        *_reading(session, workspace_dir),
        "",
        "While you are here:",
        "",
        *_rules(session),
    ]
    return {
        "flow": session.ref.name,
        "workspace": root,
        "command": executable(),
        "text": "\n".join(lines),
    }


def executable() -> str:
    """The `lumlflow` a config snippet can actually spawn.

    The console script beside the interpreter serving this workspace first: an
    install into a venv answers to no bare `lumlflow`, and naming one anyway
    would hand the reader a configuration that cannot start.
    """
    named = "lumlflow.exe" if os.name == "nt" else "lumlflow"
    beside = Path(sys.executable).parent / named
    if beside.exists():
        return str(beside)
    return shutil.which("lumlflow") or "lumlflow"


def _snippet(root: str) -> list[str]:
    """The hookup, in the shape every MCP-capable harness reads it in.

    Laid out rather than dumped: `json.dumps` breaks a three-word argument list
    over five lines, and a snippet is read as much as it is pasted.
    """
    command = json.dumps(executable())
    args = ", ".join(json.dumps(word) for word in ("mcp", "--workspace", root))
    return [
        "```json",
        "{",
        '  "mcpServers": {',
        f'    "{SERVER_NAME}": {{',
        f'      "command": {command},',
        f"      \"args\": [{args}]",
        "    }",
        "  }",
        "}",
        "```",
    ]


def _para(body: str) -> list[str]:
    return _wrapped(body)


def _bullet(body: str) -> list[str]:
    """A list item, wrapped under its own bullet rather than back to the margin."""
    return _wrapped(body, indent="  ")


def _wrapped(body: str, *, indent: str = "") -> list[str]:
    """Wrapped at whitespace and nowhere else.

    Neither long words nor hyphens are broken, because every long token in this
    text is a path or a flag: `/home/you/my-project` split across two lines is a
    path somebody pastes half of, and it overflows the column far less often
    than it would be wrong.
    """
    return textwrap.wrap(
        body,
        width=_WIDTH,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _reading(session: "FlowSession", workspace_dir: Path) -> list[str]:
    """Where an agent learns the flow — the tool first, the files behind it.

    `context` before either file: the files say what a flow is, and only the
    tool says what this one is *doing* — which lane, what is stale and
    why, what failed last.
    """
    checkout = session.ref.path / STORE_DIRNAME / CHECKOUT_NAME
    reading = [
        "- Call `context`. It names the lane you are on, what is stale and "
        "why, and what failed.",
        f"- Read `{workspace_dir / AGENTS_NAME}`. It holds the cell DSL and "
        "the verbs.",
    ]
    if session.worktree.bound() is not None:
        reading.append(f"- Read `{checkout}`. It says what the files hold.")
    return [line for item in reading for line in _bullet(item)]


def _rules(session: "FlowSession") -> list[str]:
    """The standing rules, and only the ones this flow can be got wrong on.

    The first differs by whether this flow has files at all: a flow with files
    is edited by editing them, and one without has none to name — telling an
    agent to edit `cells/` in a store-only flow sends it to write a file the
    runtime will never read.
    """
    cells = f"{session.ref.relpath}/{CELLS_DIRNAME}/"
    if session.worktree.bound() is not None:
        first = (
            f"- Cells are files under `{cells}`, one class each. Editing the "
            "file edits the cell. The `edit-cell` and `new-cell` tools do the "
            "same thing where you have no file tools."
        )
    else:
        first = (
            "- This flow has no files on disk. Its cells live in the store. "
            "Change them with `new-cell` and `edit-cell`."
        )
    rules = [
        first,
        "- Run a cell through the `run` tool. Never execute a cell file. "
        "Nothing in a cell runs at edit time. A run is what records a result.",
        "- Cells are non-interactive. `input()` fails immediately. Pass values "
        'through `params`, and secrets through `ctx.secret("NAME")`.',
        "- Every change takes an `intent`. Write one line saying why. This "
        "flow's history reads it back.",
    ]
    return [line for item in rules for line in _bullet(item)]
