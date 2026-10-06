import contextlib
import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TextIO
from urllib.parse import quote, unquote, urlsplit

from lumlflow import __version__
from lumlflow.flow.daemon import client, docs, harnesses
from lumlflow.flow.daemon.client import DaemonClient
from lumlflow.flow.errors import (
    BranchNotFound,
    CellNotFound,
    FlowError,
    FlowNotFound,
    ServerError,
)

PROTOCOL_VERSION = "2025-06-18"
_SPOKEN = frozenset({"2024-11-05", "2025-03-26", PROTOCOL_VERSION})

_FLOW_SCHEME = "flow"
GUIDE_URI = "lumlflow://guide"

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
PARSE_ERROR = -32700
RESOURCE_NOT_FOUND = -32002

INSTRUCTIONS = (
    "Call `context` first, then read `lumlflow://guide`. Context names the lane, "
    "what is stale and why, what broke, and the last whole rewrite of `cells/`. "
    "An edit on the checked-out lane is written to `cells/` at once; an edit "
    "on another lane stays in the store. `lumlflow lane use` rewrites `cells/` "
    "for the lane it checks out, while `lumlflow rewind` and `lumlflow adopt` "
    "rewrite them when they target the checked-out lane."
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
_DIRECTORY = _Arg(
    "directory",
    "string",
    "Directory whose flows to list or where the new flow is created. Defaults "
    "to the server's spawn directory.",
)
_BRANCH = _Arg("lane", "string", "Which lane. Defaults to the one you are on.")
_INTENT = _Arg(
    "intent",
    "string",
    "Why you are doing this, in a few words. It rides into the journal beside "
    "the change. This flow's history reads it back.",
    required=True,
)

_WIRE_NAMES = {
    "lane": "branch",
    "from_lane": "from_branch",
    "lanes": "branches",
}

_ALIASES = {
    "branch": "lane",
    "from_branch": "from_lane",
    "branches": "lanes",
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
        (
            _Arg("flow", "string", "Narrow the answer to one flow."),
            _DIRECTORY,
        ),
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
            _DIRECTORY,
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
            _Arg(
                "all_outputs",
                "boolean",
                "Wire every output instead of the first non-experiment output.",
            ),
            _Arg("anchor", "string", "Place the new cell directly after this cell."),
            _Arg("docstring", "string", "What the cell is for."),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "edit-cell",
        "cells.edit",
        "Replace a cell's source. On the checked-out lane lumlflow writes it "
        "to `cells/` at once, and attributes it to this session.",
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
        "move-cell",
        "cells.reorder",
        "Move a cell directly before or after another cell. Give exactly one "
        "of `before` and `after`.",
        (
            _Arg("slug", "string", "The cell to move.", required=True),
            _Arg("before", "string", "Place it directly before this cell."),
            _Arg("after", "string", "Place it directly after this cell."),
        ),
        writes=True,
    ),
    _Tool(
        "run",
        "run",
        "Run a cell, or every leaf on the lane when no cell is named, and "
        "whatever it needs first. Answers with what ran, what came from the "
        "cache, and what failed.",
        (_Arg("target", "string", "A cell, as `cell` or `cell.output`."),),
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
        "Move a lane to a step, from the recent transactions `context` "
        "lists. This is instant, nothing recomputes, and no step is added: the "
        "lane stands there until the next change on it. To change things from "
        "there without moving this lane on, start a lane with `new-lane` first.",
        (
            _Arg("to_step", "integer", "The step to restore to.", required=True),
            _INTENT,
        ),
        writes=True,
    ),
    _Tool(
        "checkpoint",
        "checkpoint",
        "Mark a step on the lane under your own words, so it can be found "
        "again. The words attach to the step itself — the lane's newest one "
        "unless `step` names another — so nothing is copied, frozen or added. "
        "`context` reads the lane's latest one back.",
        (
            _Arg(
                "step",
                "integer",
                "The step to mark. Defaults to the lane's newest step.",
            ),
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

_BY_NAME = {tool.name: tool for tool in TOOLS}


class _Refused(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _Flow:
    name: str
    path: str
    branch: str


class Server:
    def __init__(self, directory: Path, *, label: str | None = None) -> None:
        self.directory = directory.resolve()
        self.given = (label or "").strip()
        self.label = self.given or "mcp"
        self.actor = f"{self.label}-{os.getpid()}"
        self._daemon: DaemonClient | None = None
        self._named: dict[str, str] = {}
        self._flows: dict[str, _Flow] = {}
        self._registered: set[str] = set()

    def dispatch(self, line: str) -> dict[str, Any] | None:
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
            return _failed(request_id, INVALID_REQUEST, str(failure))
        except Exception as failure:
            traceback.print_exc()
            return _failed(request_id, INTERNAL_ERROR, str(failure))
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def close(self) -> None:
        for path in sorted(self._registered):
            with contextlib.suppress(FlowError, OSError):
                self._call("agent.end", {"flow": path, "actor": self.actor})
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
        info = params.get("clientInfo") or {}
        named = str(info.get("name") or "").strip()
        explicit = os.environ.get(harnesses.ACTOR_ENV, "").strip()
        registered = harnesses.client_harness_id(named)
        self.label = self.given or explicit or registered or named or "mcp"
        self.actor = f"{self.label}-{os.getpid()}"
        asked = str(params.get("protocolVersion") or "")
        return {
            "protocolVersion": asked if asked in _SPOKEN else PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "lumlflow", "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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
        flow = self._touch(params.get("flow"))
        params["flow"] = flow.path
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
            for row in self._call("tree", {"flow": flow.path})["branches"]
        ]
        if wanted not in known:
            raise BranchNotFound(
                f"no lane `{wanted}` in `{flow.name}`. there is {_listed(known)}"
            )
        flow.branch = wanted
        return {"flow": flow.name, "branch": wanted, "projected": None}

    def _resources(self) -> list[dict[str, Any]]:
        listed: list[dict[str, Any]] = [
            {
                "uri": GUIDE_URI,
                "name": "lumlflow agent guide",
                "description": "The cell DSL, lane rules, tools and CLI verbs.",
                "mimeType": "text/markdown",
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
                "cells.list", {"flow": flow.path, "branch": flow.branch}
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
        if uri == GUIDE_URI:
            return {
                "uri": uri,
                "mimeType": "text/markdown",
                "text": docs.CHEATSHEET,
            }
        parts = urlsplit(uri)
        if parts.scheme != _FLOW_SCHEME or not parts.netloc:
            raise _Refused(RESOURCE_NOT_FOUND, f"nothing is served at `{uri}`")
        route = parts.path.strip("/").split("/")
        try:
            flow = self._flow(unquote(parts.netloc))
            scoped = {"flow": flow.path, "branch": flow.branch}
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
            self._flow(str(flow["path"])) for flow in self._call("status", {})["flows"]
        ]

    def _touch(self, named: Any) -> _Flow:
        flow = self._flow(named)
        if flow.path not in self._registered:
            # Recorded only once the journal holds it. A begin that did not
            # land leaves nothing named after this session, and the end it
            # would be owed resolves to whoever *is* registered — the agent
            # working in the files, told to stop by a session it never knew.
            self._register(flow)
            self._registered.add(flow.path)
        return flow

    def _register(self, flow: _Flow) -> None:
        self._call(
            "agent.begin",
            {
                "flow": flow.path,
                "actor": self.actor,
                "label": self.label,
                "lease": True,
            },
        )

    def _flow(self, named: Any) -> _Flow:
        key = str(named) if named else ""
        path = self._named.get(key)
        if path is None:
            opened = self._call("flow.open", {"flow": named, "worktree": False})
            path = str(opened["path"])
            self._named[key] = path
            self._named[path] = path
            self._flows.setdefault(
                path,
                _Flow(
                    name=str(opened["flow"]),
                    path=path,
                    branch=str(opened["branch"]),
                ),
            )
        return self._flows[path]

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
            daemon = self._daemon = client.connect(self.directory)
        payload = {"actor": self.actor, "directory": str(self.directory)} | params
        if "directory" in params:
            asked = Path(str(params["directory"])).expanduser()
            if not asked.is_absolute():
                asked = self.directory / asked
            payload["directory"] = str(asked.resolve())
        try:
            return daemon.call(method, payload)
        except ServerError:
            self._daemon = None
            self._registered.clear()
            raise


def serve(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    directory: Path | None = None,
    label: str | None = None,
) -> int:
    reader = stdin if stdin is not None else sys.stdin
    writer = stdout if stdout is not None else sys.stdout
    _as_utf8(reader)
    _as_utf8(writer, newline="\n")
    server = Server(directory or Path.cwd(), label=label)
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
    return f"{_FLOW_SCHEME}://{quote(flow.path, safe='')}/{'/'.join(route)}"


def _failed(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _as_read(arguments: dict[str, Any]) -> dict[str, Any]:
    read = dict(arguments)
    for alias, name in _ALIASES.items():
        if alias in read:
            read.setdefault(name, read.pop(alias))
    return read


def _as_wire(params: dict[str, Any]) -> dict[str, Any]:
    wire = {_WIRE_NAMES.get(name, name): value for name, value in params.items()}
    if wire.pop("all_outputs", False):
        wire["outputs"] = "all"
    return wire


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _listed(names: list[str]) -> str:
    if len(names) == 1:
        return f"`{names[0]}`"
    return ", ".join(f"`{name}`" for name in names[:-1]) + f" and `{names[-1]}`"
