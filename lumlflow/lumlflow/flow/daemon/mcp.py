"""The MCP server: this workspace's daemon, spoken over stdio.

Strictly a wrapper. Every tool here is a daemon call and nothing else, so an
agent driving a flow through MCP and one driving it through `lumlflow` verbs
reach the same store through the same door and cannot end up disagreeing about
what a run did.

The connection is the session. A client's handshake names it, the first tool
that addresses a flow registers it there, and the hang-up ends it — so an agent
is paired by connecting and by nothing else, and no harness has to be launched
through a wrapper to be attributed.

The session never materializes a worktree: no projection, no file plane. Cells
live in the store, and attribution rides on the ops the session invokes rather
than on who happened to be editing files at the time. `use-lane` follows from
that — it moves this session's active lane and nothing else, because putting
a lane's cells on disk is a gesture only somebody with files performs.

It does take the files' *ownership*, once, when it first changes something in a
flow somebody has checked out — because from that moment the agent on the other
end is working here, and a flow whose files are rewritten under a working agent
is the one thing the worktree lock exists to prevent. Reading takes nothing:
orientation must never be the reason a human cannot check a branch out.

The transport is MCP's: JSON-RPC 2.0, one message per line, stdin to stdout.
Nothing else may be written to stdout — it is the protocol.
"""

import contextlib
import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TextIO
from urllib.parse import urlsplit

from lumlflow import __version__
from lumlflow.flow.daemon import client, workspace
from lumlflow.flow.daemon.client import DaemonClient
from lumlflow.flow.errors import (
    BranchNotFound,
    CellNotFound,
    FlowError,
    FlowNotFound,
    ServerError,
)

PROTOCOL_VERSION = "2025-06-18"
# Older clients are answered in the version they asked for. The wire shape this
# server uses — initialize, tools, resources — has not moved across these.
_SPOKEN = frozenset({"2024-11-05", "2025-03-26", PROTOCOL_VERSION})

FOCUS_URI = "session://focus"
_FLOW_SCHEME = "flow"

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
PARSE_ERROR = -32700
RESOURCE_NOT_FOUND = -32002

INSTRUCTIONS = (
    "Read `context` first. It names the lane you are on, what is stale and "
    "why, and what broke. Address a cell by name (`features`), an output as "
    "`cell.output`, and a lane by name. Your edits land in the store. "
    "Nothing here writes files or puts a lane on disk."
)

Scope = Literal["workspace", "flow", "branch"]


@dataclass(frozen=True)
class _Arg:
    name: str
    type: str
    describe: str
    required: bool = False


@dataclass(frozen=True)
class _Tool:
    """A tool and the daemon method it is. `scope` says what it addresses.

    `workspace` tools take the flow as an ordinary argument or not at all;
    `flow` and `branch` ones resolve which flow they mean — and register the
    session with it — with `branch` additionally defaulting to the branch this
    session is on.

    `writes` says the tool changes the flow, which is what takes the files: a
    session that has only read is not working here yet.
    """

    name: str
    method: str
    describe: str
    args: tuple[_Arg, ...] = ()
    scope: Scope = "branch"
    writes: bool = False

    @property
    def arguments(self) -> tuple[_Arg, ...]:
        if self.scope == "workspace":
            return self.args
        if self.scope == "flow":
            return (*self.args, _FLOW)
        return (*self.args, _FLOW, _BRANCH)

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                argument.name: _property(argument) for argument in self.arguments
            },
            "required": [
                argument.name for argument in self.arguments if argument.required
            ],
        }


_FLOW = _Arg("flow", "string", "Which flow, when the workspace holds several.")
_BRANCH = _Arg("lane", "string", "Which lane. Defaults to the one you are on.")
_INTENT = _Arg(
    "intent",
    "string",
    "Why you are doing this, in a few words. It rides into the journal beside "
    "the change. This flow's history reads it back.",
    required=True,
)

#: What the wire calls the arguments a reader now sees under lane names. The
#: daemon's params did not move, so the schema a reader learns and the payload
#: the daemon answers are two spellings of one argument.
_WIRE_NAMES = {
    "lane": "branch",
    "from_lane": "from_branch",
    "lanes": "branches",
}

#: Every spelling that still arrives, mapped onto the one a tool declares. A
#: mid-session client holds a cached schema, and there have been two of them:
#: the wire's own names and the `variant` pass between them. All three answer.
_ALIASES = {
    "branch": "lane",
    "variant": "lane",
    "from_branch": "from_lane",
    "from_variant": "from_lane",
    "branches": "lanes",
    "variants": "lanes",
}

TOOLS: tuple[_Tool, ...] = (
    _Tool(
        "context",
        "context",
        "Where you are. Names the lane, the checkpoint, what is stale and "
        "why, what failed, and what the pending work costs. Read this first.",
        scope="branch",
    ),
    _Tool(
        "status",
        "status",
        "The workspace, the flows in it, and what is stale in each.",
        (_Arg("flow", "string", "Narrow the answer to one flow."),),
        scope="workspace",
    ),
    _Tool(
        "init-flow",
        "flow.init",
        "Create a flow in this workspace. Its cells live in the store. "
        "lumlflow writes no files until somebody puts a lane on disk.",
        (
            _Arg(
                "name",
                "string",
                "What to call it. The directory becomes `<name>.flow`.",
                required=True,
            ),
        ),
        scope="workspace",
    ),
    _Tool(
        "new-cell",
        "cells.new",
        "Add a cell. Give it a name. lumlflow scaffolds an unnamed cell under "
        "a placeholder and flags it until you rename it.",
        (
            _Arg("slug", "string", "The cell's name, lowercase."),
            _Arg("source", "string", "The whole cell file. Scaffolded when absent."),
            _Arg("after", "string", "Prefill `consumes` from this cell's outputs."),
            _Arg("docstring", "string", "What the cell is for."),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "edit-cell",
        "cells.edit",
        "Replace a cell's source. lumlflow writes the version to the store "
        "and attributes it to this session.",
        (
            _Arg("slug", "string", "The cell to replace.", required=True),
            _Arg("source", "string", "Its new source, in full.", required=True),
            _Arg(
                "base",
                "string",
                "The version this edit started from, from `cells show`. Hand "
                "it back. lumlflow then tells you when a newer version landed "
                "instead of overwriting somebody.",
            ),
            _Arg("force", "boolean", "Overwrite a newer version."),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "run",
        "run",
        "Run a cell, and whatever it needs first. Answers with what ran, what "
        "came from the cache, and what failed.",
        (
            _Arg(
                "target", "string", "A cell, as `cell` or `cell.output`.", required=True
            ),
        ),
        writes=True,
    ),
    _Tool(
        "asset-preview",
        "asset.preview",
        "What a cell produced, read from the stored preview. No kernel starts.",
        (
            _Arg(
                "target", "string", "A cell, as `cell` or `cell.output`.", required=True
            ),
        ),
    ),
    _Tool(
        "new-lane",
        "fork",
        "Start a lane. One row. No file and no value is copied. The new "
        "lane keeps the versions this one has pinned.",
        (
            _Arg("name", "string", "The new lane's name.", required=True),
            _Arg(
                "from_lane",
                "string",
                "The lane to start from. Defaults to yours.",
            ),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "use-lane",
        "",
        "Work on another lane. This moves your session and nothing else. "
        "lumlflow writes no files and puts nothing on disk.",
        (_Arg("lane", "string", "The lane to work on.", required=True),),
        scope="flow",
    ),
    _Tool(
        "rewind",
        "rewind",
        "Restore a lane to a step, from the recent transactions `context` "
        "lists. This is instant. Nothing recomputes.",
        (
            _Arg("to_step", "integer", "The step to restore to.", required=True),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "adopt",
        "adopt",
        "Take one cell's version from another lane onto this one.",
        (
            _Arg("slug", "string", "The cell to take.", required=True),
            _Arg(
                "from_lane",
                "string",
                "The lane to take it from.",
                required=True,
            ),
            _Arg("force", "boolean", "Take the incoming side of a conflict."),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "diff",
        "diff",
        "How lanes differ. Cells whose code diverged first, then differing "
        "results, then everything shapeless.",
        (
            _Arg(
                "lanes",
                "array",
                "Two to five lane names.",
                required=True,
            ),
        ),
        scope="flow",
    ),
)

#: The names two of these tools answered to before lanes got their word — git's
#: spellings, then the `variant` pass. Each is kept callable so an agent holding
#: a tool list from before either rename does not break mid-session, and left
#: out of `tools/list` so a fresh one never learns them.
_RETIRED_NAMES = {
    "fork": "new-lane",
    "switch": "use-lane",
    "new-variant": "new-lane",
    "use-variant": "use-lane",
}

_BY_NAME = {tool.name: tool for tool in TOOLS}
_BY_NAME |= {was: _BY_NAME[now] for was, now in _RETIRED_NAMES.items()}


class _Refused(Exception):
    """A message this server will not answer at all, as opposed to a tool that
    failed — the JSON-RPC error the client gets back."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _Flow:
    """A flow this session addresses, and the branch it is working on.

    `checked_out` is whether it has files at all, which decides whether there
    is anything for this session to own; `owns` is whether it has taken them.
    """

    name: str
    branch: str
    checked_out: bool = False
    owns: bool = False


class Server:
    def __init__(self, root: Path, *, label: str | None = None) -> None:
        self.root = root
        # Named by whoever started this process, when they said — a harness
        # that spawns MCP servers under a generic name is told apart from the
        # next one by the `--label` its configuration carries, not by luck.
        self.given = (label or "").strip()
        self.label = self.given or "mcp"
        # One MCP server process is one session, so its pid is what separates
        # this session's ops from a second client's under the same name.
        self.actor = f"{self.label}-{os.getpid()}"
        self._daemon: DaemonClient | None = None
        self._named: dict[str, str] = {}
        self._flows: dict[str, _Flow] = {}
        self._registered: set[str] = set()
        self._active: str | None = None

    def dispatch(self, line: str) -> dict[str, Any] | None:
        """One message in, one message out — or none, for a notification."""
        try:
            message = json.loads(line)
        except ValueError:
            return _failed(None, PARSE_ERROR, "unreadable message")
        if not isinstance(message, dict) or "method" not in message:
            return _failed(None, INVALID_REQUEST, "unreadable message")
        request_id = message.get("id")
        try:
            result = self._answer(
                str(message["method"]), message.get("params") or {}, request_id
            )
        except _Refused as refused:
            return _failed(request_id, refused.code, str(refused))
        except FlowError as failure:
            # Reading a resource is not a tool call, so a runtime failure has
            # nowhere to go but the protocol.
            return _failed(request_id, INVALID_REQUEST, str(failure))
        except Exception as failure:
            # One message this server could not answer is not the end of the
            # session — the client is mid-conversation, and the trace belongs on
            # stderr where it does not corrupt the one on stdout.
            traceback.print_exc()
            return _failed(request_id, INTERNAL_ERROR, str(failure))
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def close(self) -> None:
        """End every session this one opened, and let the daemon go.

        A stdio server's disconnect is stdin closing, so this is where the
        `agent_end` the pair panel waits for comes from. It is best-effort by
        necessity: a daemon that has already gone cannot be told anything, and
        the session has ended either way.
        """
        for name in sorted(self._registered):
            with contextlib.suppress(FlowError, OSError):
                self._call("agent.end", {"flow": name, "actor": self.actor})
        self._registered.clear()
        if self._daemon is not None:
            self._daemon.close()
            self._daemon = None

    def _answer(
        self, method: str, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        if method == "initialize":
            return self._initialize(params)
        if request_id is None:
            # Every notification MCP defines is about the client's own state.
            return {}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [_described(tool) for tool in TOOLS]}
        if method == "tools/call":
            return self._call_tool(
                str(params.get("name") or ""), dict(params.get("arguments") or {})
            )
        if method == "resources/list":
            return {"resources": self._resources()}
        if method == "resources/read":
            return {"contents": [self._resource(str(params.get("uri") or ""))]}
        raise _Refused(METHOD_NOT_FOUND, f"no method `{method}`")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Who is calling, and in which version of the protocol.

        The client's name is what the session is registered under, so the pair
        panel and the journal say `claude` rather than `agent` — unless the
        configuration that spawned this process already said what to call it,
        which is the more deliberate of the two answers and wins.
        """
        info = params.get("clientInfo") or {}
        named = str(info.get("name") or "").strip()
        self.label = self.given or named or "mcp"
        self.actor = f"{self.label}-{os.getpid()}"
        asked = str(params.get("protocolVersion") or "")
        return {
            "protocolVersion": asked if asked in _SPOKEN else PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "lumlflow", "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """A tool's answer, or the sentence saying why there isn't one.

        A failure the runtime named comes back as tool output rather than as a
        protocol error: it is the caller's to act on — a branch name that does
        not exist is a typo to fix, not a session to tear down.
        """
        tool = _BY_NAME.get(name)
        if tool is None:
            raise _Refused(METHOD_NOT_FOUND, f"no tool `{name}`")
        try:
            result = self._invoke(tool, arguments)
        except FlowError as failure:
            return {"content": [_text(str(failure))], "isError": True}
        return {"content": [_text(json.dumps(result, indent=2, ensure_ascii=False))]}

    def _invoke(self, tool: _Tool, arguments: dict[str, Any]) -> Any:
        given = _as_read(arguments)
        missing = [
            argument.name
            for argument in tool.arguments
            if argument.required and _blank(given.get(argument.name))
        ]
        if missing:
            raise FlowError(f"`{tool.name}` needs {_listed(missing)}")
        params = {
            argument.name: given[argument.name]
            for argument in tool.arguments
            if not _blank(given.get(argument.name))
        }
        if tool.scope == "workspace":
            return self._call(tool.method, _as_wire(params))
        flow = self._touch(params.get("flow"), writes=tool.writes)
        params["flow"] = flow.name
        if tool.name == "use-lane":
            return self._use(flow, str(params["lane"]))
        if tool.scope == "branch":
            params.setdefault("lane", flow.branch)
        return self._call(tool.method, _as_wire(params))

    def _use(self, flow: _Flow, wanted: str) -> dict[str, Any]:
        """Move this session onto another lane — and only this session.

        The files belong to whoever has them. A session that never projected
        any cannot put a lane on disk, and doing it anyway would rewrite a
        directory somebody else is working in.
        """
        known = [
            str(row["branch"])
            for row in self._call("tree", {"flow": flow.name})["branches"]
        ]
        if wanted not in known:
            raise BranchNotFound(
                f"no lane `{wanted}` in `{flow.name}`. there is {_listed(known)}"
            )
        flow.branch = wanted
        return {"flow": flow.name, "branch": wanted, "projected": None}

    def _resources(self) -> list[dict[str, Any]]:
        """Everything readable: the brief, then each flow's cells and results.

        Enumerated against the branch this session is on rather than whichever
        one has files, so a session that switched reads its own branch back.
        """
        listed = [
            {
                "uri": FOCUS_URI,
                "name": "focus",
                "description": "Where this session stands, and what needs doing.",
                "mimeType": "application/json",
            }
        ]
        for flow in self._all_flows():
            listed.append(
                {
                    "uri": _uri(flow, "manifest"),
                    "name": f"{flow.name} manifest",
                    "description": f"The cells on `{flow.branch}` and how each stands.",
                    "mimeType": "application/json",
                }
            )
            for cell in self._call(
                "cells.list", {"flow": flow.name, "branch": flow.branch}
            )["cells"]:
                slug = str(cell["slug"])
                listed.append(
                    {
                        "uri": _uri(flow, "cells", slug),
                        "name": f"{flow.name}/{slug}",
                        "description": f"The source of `{slug}`.",
                        "mimeType": "text/x-python",
                    }
                )
                listed.extend(
                    {
                        "uri": _uri(flow, "previews", f"{slug}.{output}"),
                        "name": f"{flow.name}/{slug}.{output}",
                        "description": f"What `{slug}` produced as `{output}`.",
                        "mimeType": "application/json",
                    }
                    for output in cell["outputs"]
                )
        return listed

    def _resource(self, uri: str) -> dict[str, Any]:
        """What a URI reads as, on the branch this session is on.

        A name the flow does not know is answered as a missing resource rather
        than as a failure, which is what lets a client tell a stale URI from a
        runtime that is not answering.
        """
        if uri == FOCUS_URI:
            flow = self._flow(self._active)
            return _json_content(
                uri, self._call("context", {"flow": flow.name, "branch": flow.branch})
            )
        parts = urlsplit(uri)
        if parts.scheme != _FLOW_SCHEME or not parts.netloc:
            raise _Refused(RESOURCE_NOT_FOUND, f"nothing is served at `{uri}`")
        route = parts.path.strip("/").split("/")
        try:
            flow = self._flow(parts.netloc)
            scoped = {"flow": flow.name, "branch": flow.branch}
            if route == ["manifest"]:
                return _json_content(uri, self._call("cells.list", scoped))
            if len(route) == 2 and route[0] == "cells":
                shown = self._call("cells.show", scoped | {"slug": route[1]})
                return {
                    "uri": uri,
                    "mimeType": "text/x-python",
                    "text": shown["source"],
                }
            if len(route) == 2 and route[0] == "previews":
                return _json_content(
                    uri, self._call("asset.preview", scoped | {"target": route[1]})
                )
        except (CellNotFound, FlowNotFound) as unknown:
            raise _Refused(RESOURCE_NOT_FOUND, str(unknown)) from unknown
        raise _Refused(RESOURCE_NOT_FOUND, f"nothing is served at `{uri}`")

    def _all_flows(self) -> list[_Flow]:
        return [
            self._flow(str(flow["flow"])) for flow in self._call("status", {})["flows"]
        ]

    def _touch(self, named: Any, *, writes: bool = False) -> _Flow:
        """The flow a tool means, registered with the first time one addresses it.

        Registration is what the pair panel detects, so it is driving that opens
        it — a client listing resources to fill a picker has not started work
        here and is not announced as though it had. Driving is also what makes a
        flow this session's active one, which is the flow `session://focus`
        answers for.

        The first tool that *changes* something takes the flow's files with it,
        where there are files: from then on the agent's own edits to `cells/`
        are attributed to this session rather than to the human sitting in the
        same directory, and nothing rewrites those files under it. A session
        that only reads owns nothing, so orientation never blocks a checkout.
        """
        flow = self._flow(named)
        self._active = flow.name
        if flow.name not in self._registered:
            # Recorded only once the journal holds it. A begin that did not
            # land leaves nothing named after this session, and the end it
            # would be owed resolves to whoever *is* registered — the agent
            # working in the files, told to stop by a session it never knew.
            self._register(flow, worktree=False)
            self._registered.add(flow.name)
        if writes and flow.checked_out and not flow.owns:
            self._register(flow, worktree=True)
            flow.owns = True
        return flow

    def _register(self, flow: _Flow, *, worktree: bool) -> None:
        """Open — or widen — this session's registration on a flow.

        Leased: the daemon ends what this connection opened when the connection
        goes, so a client that is killed rather than closed leaves no session
        standing and no files held by nobody.
        """
        self._call(
            "agent.begin",
            {
                "flow": flow.name,
                "actor": self.actor,
                "label": self.label,
                "worktree": worktree,
                "lease": True,
            },
        )

    def _flow(self, named: Any) -> _Flow:
        """Resolve a flow once, and remember which branch this session is on.

        Which flow an unnamed call addresses is the daemon's answer to give —
        the error naming the candidates is worth more than a guess here. Opening
        it `worktree: false` is the whole MCP path in one argument: learn the
        branch to answer for, and leave the files alone.

        The answer is remembered per spelling, so a session that started
        addressing the workspace's only flow keeps addressing it after a second
        one is created rather than being asked which it meant halfway through.
        """
        key = str(named) if named else ""
        name = self._named.get(key)
        if name is None:
            opened = self._call("flow.open", {"flow": named, "worktree": False})
            name = str(opened["flow"])
            self._named[key] = name
            self._flows.setdefault(
                name,
                _Flow(
                    name=name,
                    branch=str(opened["branch"]),
                    checked_out=bool(opened.get("checked_out")),
                ),
            )
        return self._flows[name]

    def _call(self, method: str, params: dict[str, Any]) -> Any:
        """One daemon call, over a connection this session keeps open.

        A dropped connection is dropped for good: whatever it was carrying, it
        will not say, and a call that may already have landed must not be
        replayed on a guess. The next call starts a daemon and carries on.

        The sessions this one opened were leased to that connection, so a drop
        ends them wherever the daemon still is. Forgetting them here is what
        lets the next flow this session touches register again instead of
        working on under a bracket nobody is holding open.
        """
        daemon = self._daemon
        if daemon is None:
            daemon = self._daemon = client.connect(self.root)
        try:
            return daemon.call(method, {"actor": self.actor} | params)
        except ServerError:
            self._daemon = None
            self._registered.clear()
            for flow in self._flows.values():
                flow.owns = False
            raise


def serve(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    root: Path | None = None,
    label: str | None = None,
) -> int:
    """Answer MCP over stdio until the client hangs up."""
    reader = stdin if stdin is not None else sys.stdin
    writer = stdout if stdout is not None else sys.stdout
    _as_utf8(reader)
    _as_utf8(writer, newline="\n")
    server = Server(
        root if root is not None else workspace.resolve_root(Path.cwd()), label=label
    )
    try:
        while line := reader.readline():
            if not line.strip():
                continue
            answer = server.dispatch(line)
            if answer is None:
                continue
            writer.write(json.dumps(answer, ensure_ascii=False) + "\n")
            writer.flush()
    finally:
        server.close()
    return 0


def _as_utf8(stream: TextIO, newline: str | None = None) -> None:
    """MCP is UTF-8 and newline-framed on every platform this runs on."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):
        reconfigure(encoding="utf-8", newline=newline)


def _described(tool: _Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.describe,
        "inputSchema": tool.schema,
    }


def _property(argument: _Arg) -> dict[str, Any]:
    described: dict[str, Any] = {
        "type": argument.type,
        "description": argument.describe,
    }
    if argument.type == "array":
        described["items"] = {"type": "string"}
    return described


def _text(body: str) -> dict[str, str]:
    return {"type": "text", "text": body}


def _json_content(uri: str, body: Any) -> dict[str, Any]:
    return {
        "uri": uri,
        "mimeType": "application/json",
        "text": json.dumps(body, indent=2, ensure_ascii=False),
    }


def _uri(flow: _Flow, *route: str) -> str:
    return f"{_FLOW_SCHEME}://{flow.name}/{'/'.join(route)}"


def _failed(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _as_read(arguments: dict[str, Any]) -> dict[str, Any]:
    """Arguments under the names a reader sees, whichever spelling arrived."""
    read = dict(arguments)
    for alias, name in _ALIASES.items():
        if alias in read:
            read.setdefault(name, read.pop(alias))
    return read


def _as_wire(params: dict[str, Any]) -> dict[str, Any]:
    """Arguments under the names the daemon has always answered to."""
    return {_WIRE_NAMES.get(name, name): value for name, value in params.items()}


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _listed(names: list[str]) -> str:
    if len(names) == 1:
        return f"`{names[0]}`"
    return ", ".join(f"`{name}`" for name in names[:-1]) + f" and `{names[-1]}`"
