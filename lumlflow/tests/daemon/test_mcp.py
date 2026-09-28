"""The MCP server, driven the way a client drives it.

Messages go in on stdin and come back on stdout, and behind the socket is the
same API every verb goes through — so what these exercise is the whole path an
agent takes: the protocol, the tool, the daemon, the store, and a real kernel.

The point of most of them is what the session does *not* do. An MCP client has
no files: nothing here may check a branch out, project a cell, take the
file plane, or attribute an op to anyone but the session that invoked it.
"""

import asyncio
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from lumlflow.flow.daemon import client, docs, mcp
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.errors import ServerError
from lumlflow.flow.store.models import AgentBegin, AgentEnd

from tests.daemon.helpers import (
    SCORE_CELL,
    LocalDaemon,
    cell_files,
    make_workspace,
    no_git_words,
    ops_of,
    slice_of,
    source_of,
    transactions,
)

SWEEP_CELL = """
class Score:
    \"\"\"The headline metric, swept.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.94}}
"""

Answers = dict[int, dict[str, Any]]


class Talk:
    """A scripted MCP client, and the store it drove.

    Calling it runs a whole session — the messages, then the hang-up — so
    `agent_end` is part of every script whether or not a test asks about it.
    """

    def __init__(
        self, hub: Hub, api: Api, loop: asyncio.AbstractEventLoop, directory: Path
    ) -> None:
        self.hub = hub
        self.api = api
        self._loop = loop
        self.directory = directory

    def __call__(self, *messages: dict[str, Any]) -> Answers:
        written = "".join(json.dumps(message) + "\n" for message in messages)
        answered = io.StringIO()
        mcp.serve(io.StringIO(written), answered, directory=self.directory)
        return {
            int(answer["id"]): answer
            for answer in map(json.loads, answered.getvalue().splitlines())
        }

    def flow(self, name: str) -> FlowSession:
        return self.hub.session(name)

    def held(self, *, label: str | None = None) -> "Held":
        """A session kept open, for the questions only a live one answers."""
        return Held(self.directory, label=label)


class Held:
    """One MCP session driven message by message, without hanging up.

    What a session *holds* — the registration, the files — is only observable
    while it is running, and `Talk` scripts a whole session including its
    hang-up. This is the same server, kept open until a test says otherwise.
    """

    def __init__(self, root: Path, *, label: str | None = None) -> None:
        self.server = mcp.Server(root, label=label)
        self.answers: Answers = {}

    def __call__(self, *messages: dict[str, Any]) -> Answers:
        for message in messages:
            answer = self.server.dispatch(json.dumps(message))
            if answer is not None:
                self.answers[int(answer["id"])] = answer
        return self.answers

    def close(self) -> None:
        self.server.close()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return make_workspace(tmp_path / "project", flows=())


@pytest.fixture
def talk(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Talk]:
    loop = asyncio.new_event_loop()
    hub = Hub()
    api = Api(hub, directory=workspace)
    monkeypatch.setattr(
        client, "connect", lambda root, **kwargs: LocalDaemon(api, loop)
    )
    try:
        yield Talk(hub, api, loop, workspace)
    finally:
        loop.run_until_complete(hub.close())
        loop.close()


def test_the_mcp_only_loop_never_materializes_a_worktree(talk: Talk, workspace: Path):
    """The scenario: a flow created and driven entirely through MCP.

    No checkout is projected, nothing watches a file that does not exist, and
    every version and every run carries the registered session's name.
    """
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(
            3, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"}
        ),
        tool(4, "run", {"target": "score"}),
        tool(5, "asset-preview", {"target": "score.summary"}),
    )

    outcome = answered(answers, 4)
    preview = answered(answers, 5)
    live = talk.flow("churn")
    begun = ops_of(live, AgentBegin)[0]
    authors = {version.author for version in slice_of(live, "main").values()}
    ran = [
        entry.actor
        for entry in transactions(live)
        if any(op.op == "run_recorded" for op in entry.ops)
    ]

    assert outcome["executed"] == ["score"] and not outcome["failed"]
    assert preview["state"] == "synced"
    assert cell_files(workspace / "churn.flow") == []
    assert live.worktree.bound() is None
    assert authors == {begun.actor} and ran == [begun.actor]
    assert answered(answers, 2)["written_to_files"] is False


def test_run_tool_accepts_no_target_and_runs_the_lane(talk: Talk) -> None:
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "run"),
    )

    outcome = answered(answers, 3)
    assert outcome["targets"] == ["score"]
    assert outcome["executed"] == ["score"]


def test_the_session_is_named_after_the_client_and_ends_when_it_hangs_up(talk: Talk):
    """Detected, never declared: the pair panel reads both of these off the
    journal, and a session that only calls the API holds no files."""
    talk(
        hello(name="claude"),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
    )

    live = talk.flow("churn")
    begun = ops_of(live, AgentBegin)
    ended = ops_of(live, AgentEnd)

    assert [op.label for op in begun] == ["claude"]
    assert "worktree" not in begun[0].model_dump()
    assert [op.actor for op in ended] == [begun[0].actor]


def test_a_session_registers_once_and_never_takes_the_files(
    talk: Talk, workspace: Path
):
    """Reading and writing share one registration; neither owns the files."""
    live = checked_out(talk, "churn", branch="sweep")
    session = talk.held()

    session(hello(name="claude"), tool(1, "context", {}))
    reading = live.store.index.agent_sessions()
    answers = session(
        tool(2, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"})
    )
    working = live.store.index.agent_sessions()
    actor = working[0].actor
    session.close()
    afterwards = live.store.index.agent_sessions()

    assert [registered.label for registered in reading] == ["claude"]
    assert [registered.label for registered in working] == ["claude"]
    assert len(ops_of(live, AgentBegin)) == 1
    assert answered(answers, 2)["written_to_files"] is True
    assert "0.94" in source_of(workspace / "churn.flow", "score")
    assert afterwards == []
    assert [op.actor for op in ops_of(live, AgentEnd)] == [actor]


def test_a_flow_with_no_files_still_has_one_plain_registration(
    talk: Talk,
):
    session = talk.held()

    session(
        hello(name="claude"),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "run", {"target": "score"}),
    )
    live = talk.flow("churn")
    registered = live.store.index.agent_sessions()
    session.close()

    assert len(registered) == 1
    assert all("worktree" not in op.model_dump() for op in ops_of(live, AgentBegin))


def test_the_label_a_configuration_gave_wins_over_environment_and_client_name(
    talk: Talk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A harness that spawns every MCP server under one generic name is told
    apart by what its configuration says, which is the deliberate answer."""
    monkeypatch.setenv("LUMLFLOW_ACTOR", "from-environment")
    session = talk.held(label="pair-1")

    session(hello(name="Claude Code"), tool(1, "init-flow", {"name": "churn"}))
    session(tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "s"}))
    live = talk.flow("churn")
    session.close()

    assert [op.label for op in ops_of(live, AgentBegin)] == ["pair-1"]
    assert {version.author for version in slice_of(live, "main").values()} == {
        ops_of(live, AgentBegin)[0].actor
    }


def test_environment_then_registry_id_precede_the_raw_mcp_client_name(
    talk: Talk, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = talk.held()
    monkeypatch.setenv("LUMLFLOW_ACTOR", "named-shell")
    explicit(
        hello(name="Claude Code"),
        tool(1, "init-flow", {"name": "explicit"}),
        tool(2, "context", {"flow": "explicit"}),
    )
    explicit.close()

    monkeypatch.delenv("LUMLFLOW_ACTOR")
    matched = talk.held()
    matched(
        hello(name="Claude Code"),
        tool(1, "init-flow", {"name": "matched"}),
        tool(2, "context", {"flow": "matched"}),
    )
    matched.close()

    assert [op.label for op in ops_of(talk.flow("explicit"), AgentBegin)] == [
        "named-shell"
    ]
    assert [op.label for op in ops_of(talk.flow("matched"), AgentBegin)] == [
        "claude-code"
    ]


def test_use_lane_moves_this_session_and_leaves_the_files_alone(
    talk: Talk, workspace: Path
):
    """The daemon's lane switch rebinds a worktree. This one cannot: it sets the
    branch this session works on, and every later tool follows it."""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "new-lane", {"name": "sweep", "intent": "try a higher lr"}),
        tool(4, "use-lane", {"lane": "sweep"}),
        tool(
            5, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"}
        ),
        tool(6, "context", {}),
        tool(7, "context", {"lane": "main"}),
    )

    live = talk.flow("churn")
    definitions = {
        branch: slice_of(live, branch)["score"].definition_hash
        for branch in ("main", "sweep")
    }

    assert answered(answers, 4) == {
        "flow": "churn",
        "branch": "sweep",
        "projected": None,
    }
    assert answered(answers, 5)["branch"] == "sweep"
    assert answered(answers, 6)["branch"] == "sweep"
    assert answered(answers, 7)["branch"] == "main"
    assert definitions["main"] != definitions["sweep"]
    assert live.worktree.bound() is None
    assert cell_files(workspace / "churn.flow") == []


def test_checkpoint_marks_the_sessions_lane_and_refuses_bad_requests(
    talk: Talk,
) -> None:
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-lane", {"name": "sweep", "intent": "trying a sweep"}),
        tool(3, "use-lane", {"lane": "sweep"}),
        tool(4, "checkpoint", {"intent": "baseline"}),
        tool(5, "context", {}),
        tool(6, "context", {"lane": "main"}),
        tool(7, "checkpoint", {}),
        tool(8, "checkpoint", {"lane": "nowhere", "intent": "x"}),
        tool(9, "context", {}),
    )

    marked = answered(answers, 4)
    sweep_context = answered(answers, 5)
    main_context = answered(answers, 6)

    assert marked["branch"] == "sweep"
    assert isinstance(marked["step"], int)
    assert marked["intent"] == "baseline"
    assert sweep_context["checkpoint"]["step"] == marked["step"]
    assert sweep_context["checkpoint"]["mark"] == "baseline"
    # The words ride on the lane's newest step rather than adding one.
    assert sweep_context["recent"][0]["step"] == marked["step"]
    assert main_context["checkpoint"] is None
    assert "`intent`" in failed(answers, 7)
    assert "nowhere" in failed(answers, 8)
    assert answered(answers, 9)["branch"] == "sweep"


def test_a_session_starts_where_the_files_are_and_use_lane_leaves_them_there(
    talk: Talk, workspace: Path
):
    """The other half of `use-lane`: a flow somebody has checked out.

    The session's branch begins as the bound one — the agent lands where the
    files are rather than on whatever `main` holds — and moving it moves
    nothing else. Rebinding the worktree is the daemon's `switch`, and an edit
    to a branch that is not the bound one is owed to no file at all.
    """
    live = checked_out(talk, "churn", branch="sweep")

    answers = talk(
        hello(),
        tool(1, "context", {}),
        tool(2, "use-lane", {"lane": "main"}),
        tool(
            3, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"}
        ),
        tool(4, "context", {}),
    )

    versions = {branch: slice_of(live, branch)["score"] for branch in ("main", "sweep")}
    bound = live.worktree.bound()

    assert answered(answers, 1)["branch"] == "sweep"
    assert answered(answers, 2) == {
        "flow": "churn",
        "branch": "main",
        "projected": None,
    }
    assert answered(answers, 3)["written_to_files"] is False
    assert answered(answers, 4)["branch"] == "main"
    assert versions["main"].definition_hash != versions["sweep"].definition_hash
    assert bound is not None and bound.name == "sweep"
    assert source_of(workspace / "churn.flow", "score") == live.store.objects.get(
        versions["sweep"].raw_source_ref
    ).decode("utf-8")


def test_a_registration_that_never_landed_ends_nobody(
    talk: Talk, monkeypatch: pytest.MonkeyPatch
):
    """A refused registration leaves no session for this client to end."""
    live = checked_out(talk, "churn", branch="sweep")
    live.store.commit(
        [AgentBegin(actor="claude-code", label="claude")],
        intent="claude started working",
        actor="claude-code",
    )

    async def refused(params: dict[str, Any]) -> Any:
        raise ServerError("lumlflow dropped `agent.begin`")

    monkeypatch.setitem(talk.api.methods, "agent.begin", refused)
    answers = talk(hello(), tool(1, "context", {}))

    registered = live.store.index.agent_sessions()

    assert "agent.begin" in failed(answers, 1)
    assert [session.actor for session in registered] == ["claude-code"]
    assert ops_of(live, AgentEnd) == []


def test_a_named_branch_that_is_not_there_fails_the_tool_not_the_session(
    talk: Talk,
):
    """A typo is the caller's to fix. The session keeps answering."""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "use-lane", {"lane": "sweep"}),
        tool(3, "run", {"target": "nowhere"}),
        tool(4, "status", {}),
    )

    refused = failed(answers, 2)

    assert "sweep" in refused and "main" in refused
    assert "nowhere" in failed(answers, 3)
    assert answered(answers, 4)["flows"][0]["flow"] == "churn"


def test_two_same_named_flows_stay_distinct_in_one_mcp_session(
    talk: Talk, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = make_workspace(workspace / "a", flows=("sales",)) / "sales.flow"
    second = make_workspace(workspace / "b", flows=("sales",)) / "sales.flow"
    addressed: list[str] = []
    context = talk.api.methods["context"]

    async def record_path(params: dict[str, Any]) -> Any:
        addressed.append(str(params.get("flow")))
        return await context(params)

    monkeypatch.setitem(talk.api.methods, "context", record_path)

    answers = talk(
        hello(),
        tool(1, "context", {"flow": str(first)}),
        tool(2, "context", {"flow": str(second)}),
        tool(3, "context", {"flow": str(first)}),
    )

    assert [answered(answers, request_id)["flow"] for request_id in (1, 2, 3)] == [
        "sales",
        "sales",
        "sales",
    ]
    assert addressed == [str(first), str(second), str(first)]
    assert talk.hub.session(str(first)) is not talk.hub.session(str(second))


def test_a_bare_duplicate_name_is_refused_with_both_paths_over_mcp(
    talk: Talk, workspace: Path
) -> None:
    first = make_workspace(workspace / "a", flows=("sales",)) / "sales.flow"
    second = make_workspace(workspace / "b", flows=("sales",)) / "sales.flow"

    answers = talk(hello(), tool(1, "context", {"flow": "sales"}))
    refusal = failed(answers, 1)

    assert str(first) in refusal
    assert str(second) in refusal


def test_status_and_init_flow_take_an_optional_directory(
    talk: Talk, workspace: Path
) -> None:
    requested = make_workspace(workspace.parent / "requested", flows=("sales",))
    relative = requested.relative_to(workspace, walk_up=True)

    answers = talk(
        hello(),
        tool(1, "status", {"directory": str(relative)}),
        tool(2, "init-flow", {"name": "sweep", "directory": str(relative)}),
    )

    status = answered(answers, 1)
    created = answered(answers, 2)
    assert [flow["path"] for flow in status["flows"]] == [str(requested / "sales.flow")]
    assert created["path"] == str(requested / "sweep.flow")
    assert (requested / "sweep.flow").is_dir()


def test_a_tool_missing_an_argument_says_which_one(talk: Talk):
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "edit-cell", {"slug": "score", "intent": "fix it"}),
    )

    assert "`source`" in failed(answers, 2)


def test_move_cell_places_a_cell_and_returns_its_order(talk: Talk) -> None:
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "first", "intent": "first"}),
        tool(3, "new-cell", {"slug": "last", "intent": "last"}),
        tool(4, "new-cell", {"slug": "moved", "intent": "moved"}),
        tool(5, "move-cell", {"slug": "moved", "before": "last"}),
    )

    moved = answered(answers, 5)
    live = talk.flow("churn")
    moved_uid = slice_of(live, "main")["moved"].uid

    assert moved["slug"] == "moved"
    assert moved["uid"] == moved_uid
    assert live.store.manifest.order == {moved_uid: moved["order"]}


def test_new_cell_all_outputs_wires_every_producer_output(talk: Talk) -> None:
    producer = """
class Train:
    produces = {"model": "model", "run": "experiment"}
"""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "train", "source": producer, "intent": "train"}),
        tool(
            3,
            "new-cell",
            {
                "slug": "report",
                "after": "train",
                "all_outputs": True,
                "intent": "report",
            },
        ),
    )

    assert answered(answers, 3)["slug"] == "report"
    live = talk.flow("churn")
    version = slice_of(live, "main")["report"]
    report = live.store.objects.get(version.raw_source_ref).decode("utf-8")
    assert 'consumes = {"model": "train.model", "run": "train.run"}' in report
    assert "def materialize(self, ctx, model, run):" in report


def test_resources_serve_the_guide_and_flow_data_and_refuse_removed_focus(
    talk: Talk, workspace: Path
):
    """The read-only half: what the flow holds, without invoking anything."""
    address = quote(str(workspace / "churn.flow"), safe="")
    root = f"flow://{address}"
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "run", {"target": "score"}),
        request(4, "resources/list"),
        request(5, "resources/read", {"uri": f"{root}/manifest"}),
        request(6, "resources/read", {"uri": f"{root}/cells/score"}),
        request(7, "resources/read", {"uri": f"{root}/previews/score.summary"}),
        request(8, "resources/read", {"uri": "session://focus"}),
        request(9, "resources/read", {"uri": "flow://churn/cells/nowhere"}),
        request(10, "resources/read", {"uri": "lumlflow://guide"}),
    )

    listed = {resource["uri"] for resource in answers[4]["result"]["resources"]}
    manifest = read(answers, 5)
    source = answers[6]["result"]["contents"][0]
    preview = read(answers, 7)
    guide = answers[10]["result"]["contents"][0]

    assert listed == {
        "lumlflow://guide",
        f"{root}/manifest",
        f"{root}/cells/score",
        f"{root}/previews/score.summary",
    }
    assert [cell["slug"] for cell in manifest["cells"]] == ["score"]
    assert source["mimeType"] == "text/x-python"
    assert "class Score" in source["text"]
    assert preview["kind"] == "metric" and preview["preview"]["blocks"]
    assert guide == {
        "uri": "lumlflow://guide",
        "mimeType": "text/markdown",
        "text": docs.CHEATSHEET,
    }
    assert answers[8]["error"]["code"] == mcp.RESOURCE_NOT_FOUND
    # A name the flow does not know reads as a missing resource, not as a
    # runtime that failed — the client can tell a stale URI from a broken one.
    assert answers[9]["error"]["code"] == mcp.RESOURCE_NOT_FOUND
    assert "nowhere" in answers[9]["error"]["message"]


def test_the_handshake_answers_in_the_version_the_client_asked_for(talk: Talk):
    """A client speaking an older revision is answered in it; one speaking
    something this server does not know is told what it does speak."""
    answers = talk(
        hello(request_id=1, version="2024-11-05"),
        hello(request_id=2, version="1999-01-01"),
        request(3, "tools/list"),
        request(4, "nonsense/method"),
    )

    old = answers[1]["result"]
    unknown = answers[2]["result"]
    tools = {tool["name"]: tool for tool in answers[3]["result"]["tools"]}

    assert old["protocolVersion"] == "2024-11-05"
    assert unknown["protocolVersion"] == mcp.PROTOCOL_VERSION
    assert old["capabilities"] == {"tools": {}, "resources": {}}
    assert set(tools) == {tool.name for tool in mcp.TOOLS}
    assert tools["edit-cell"]["inputSchema"]["required"] == ["slug", "source", "intent"]
    assert "anchor" in tools["new-cell"]["inputSchema"]["properties"]
    assert "all_outputs" in tools["new-cell"]["inputSchema"]["properties"]
    assert tools["move-cell"]["inputSchema"]["required"] == ["slug"]
    assert {"before", "after"} <= set(tools["move-cell"]["inputSchema"]["properties"])
    assert "lane" in tools["run"]["inputSchema"]["properties"]
    assert "target" not in tools["run"]["inputSchema"].get("required", [])
    assert "directory" in tools["status"]["inputSchema"]["properties"]
    assert "directory" in tools["init-flow"]["inputSchema"]["properties"]
    checkpoint_schema = tools["checkpoint"]["inputSchema"]
    assert checkpoint_schema["required"] == ["intent"]
    assert {"lane", "flow", "step"} <= set(checkpoint_schema["properties"])
    assert "force" not in checkpoint_schema["properties"]
    assert next(tool for tool in mcp.TOOLS if tool.name == "checkpoint").writes is True
    assert answers[4]["error"]["code"] == mcp.METHOD_NOT_FOUND


def test_the_handshake_tells_an_agent_what_to_read_and_when_files_move(talk: Talk):
    instructions = talk(hello())[0]["result"]["instructions"]

    assert "`context` first" in instructions
    assert "`lumlflow://guide`" in instructions
    assert "checked-out lane" in instructions
    assert "written to `cells/` at once" in instructions
    assert all(verb in instructions for verb in ("lane use", "rewind", "adopt"))
    assert "Nothing here writes files" not in instructions


def test_only_conflict_resolution_tools_declare_force() -> None:
    tools_with_force = {
        tool.name for tool in mcp.TOOLS if "force" in tool.schema["properties"]
    }

    assert tools_with_force == {"adopt", "edit-cell"}


def test_a_notification_is_not_answered(talk: Talk):
    """Ids identify answers; a message without one gets none."""
    answers = talk(
        hello(),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        request(1, "ping"),
    )

    assert answers[1]["result"] == {}
    assert set(answers) == {0, 1}


def checked_out(talk: Talk, name: str, *, branch: str) -> FlowSession:
    """A flow with a file plane, the way `lumlflow init` leaves one.

    Bound to a branch that is not `main`, so a session that lands on the right
    one is telling the bound branch from the default rather than agreeing with
    both at once.
    """
    live = talk.hub.init_flow(talk.directory, name)
    live.worktree.checkout(actor="user")
    live.acceptance.accept_source(
        "score", SCORE_CELL, branch="main", actor="user", intent="scored", fresh=True
    )
    live.store.branches.fork(branch, from_branch="main", actor="user", intent="swept")
    live.worktree.checkout(branch, actor="user")
    return live


def hello(
    *,
    request_id: int = 0,
    name: str = "claude",
    version: str = mcp.PROTOCOL_VERSION,
) -> dict[str, Any]:
    return request(
        request_id,
        "initialize",
        {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": name, "version": "1.0"},
        },
    )


def tool(
    request_id: int, name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    return request(
        request_id, "tools/call", {"name": name, "arguments": arguments or {}}
    )


def request(
    request_id: int, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


def answered(answers: Answers, request_id: int) -> Any:
    """What a tool answered, refusing to pretend a failure was one."""
    body = answers[request_id]["result"]
    assert not body.get("isError"), body["content"][0]["text"]
    return json.loads(body["content"][0]["text"])


def failed(answers: Answers, request_id: int) -> str:
    body = answers[request_id]["result"]
    assert body.get("isError"), body
    return str(body["content"][0]["text"])


def read(answers: Answers, request_id: int) -> Any:
    return json.loads(answers[request_id]["result"]["contents"][0]["text"])


def test_no_listed_tool_teaches_the_vocabulary_git_owns():
    """The tool list is the vocabulary an agent learns this product in."""
    for tool in mcp.TOOLS:
        no_git_words(tool.name, f"the `{tool.name}` tool name")
        no_git_words(tool.describe, f"the `{tool.name}` description")
        for argument in tool.arguments:
            no_git_words(argument.name, f"`{tool.name}.{argument.name}`")
            no_git_words(argument.describe, f"`{tool.name}.{argument.name}` help")
    no_git_words(mcp.INSTRUCTIONS, "the server instructions")


def test_retired_tool_names_are_unknown_and_current_names_work(
    talk: Talk, workspace: Path
):
    make_workspace(workspace, flows=("churn",))
    answers = talk(
        hello(request_id=1),
        request(2, "tools/list"),
        tool(3, "fork", {"name": "sweep", "intent": "removed"}),
        tool(4, "switch", {"lane": "sweep"}),
        tool(5, "new-variant", {"name": "second", "intent": "removed"}),
        tool(6, "use-variant", {"lane": "second"}),
        tool(7, "new-lane", {"name": "sweep", "intent": "current spelling"}),
        tool(8, "use-lane", {"lane": "sweep"}),
    )

    listed = {entry["name"] for entry in answers[2]["result"]["tools"]}
    assert {"new-lane", "use-lane"} <= listed
    assert not {"fork", "switch", "new-variant", "use-variant"} & listed
    for request_id in range(3, 7):
        assert answers[request_id]["error"]["code"] == mcp.METHOD_NOT_FOUND
        assert "no tool" in answers[request_id]["error"]["message"]
    assert answered(answers, 7)["branch"] == "sweep"
    assert answered(answers, 8)["branch"] == "sweep"


def test_retired_variant_arguments_are_not_lane_aliases(
    talk: Talk, workspace: Path
) -> None:
    make_workspace(workspace, flows=("churn",))
    answers = talk(
        hello(request_id=1),
        tool(2, "new-lane", {"name": "sweep", "intent": "current spelling"}),
        tool(3, "use-lane", {"variant": "sweep"}),
        tool(4, "context", {"variant": "sweep"}),
        tool(
            5,
            "new-lane",
            {"name": "second", "from_variant": "sweep", "intent": "no alias"},
        ),
        tool(6, "diff", {"variants": ["main", "sweep"]}),
    )

    assert "`lane`" in failed(answers, 3)
    assert answered(answers, 4)["branch"] == "main"
    assert answered(answers, 5)["from_branch"] == "main"
    assert "`lanes`" in failed(answers, 6)
