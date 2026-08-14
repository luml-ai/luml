"""The MCP server, driven the way a client drives it.

Messages go in on stdin and come back on stdout, and behind the socket is the
same API every verb goes through — so what these exercise is the whole path an
agent takes: the protocol, the tool, the daemon, the store, and a real kernel.

The point of most of them is what the session does *not* do. An MCP client has
no files: nothing here may check a branch out, project a cell, take the
worktree lock, or attribute an op to anyone but the session that invoked it.
"""

import asyncio
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import client, mcp
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

    def __init__(self, hub: Hub, api: Api, loop: asyncio.AbstractEventLoop) -> None:
        self.hub = hub
        self.api = api
        self._loop = loop

    def __call__(self, *messages: dict[str, Any]) -> Answers:
        written = "".join(json.dumps(message) + "\n" for message in messages)
        answered = io.StringIO()
        mcp.serve(io.StringIO(written), answered, root=self.hub.root)
        return {
            int(answer["id"]): answer
            for answer in map(json.loads, answered.getvalue().splitlines())
        }

    def flow(self, name: str) -> FlowSession:
        return self.hub.session(name)

    def held(self, *, label: str | None = None) -> "Held":
        """A session kept open, for the questions only a live one answers."""
        return Held(self.hub.root, label=label)


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
    hub = Hub(workspace)
    api = Api(hub)
    monkeypatch.setattr(
        client, "connect", lambda root, **kwargs: LocalDaemon(api, loop)
    )
    try:
        yield Talk(hub, api, loop)
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
    assert live.worktree.bound() is None and live.worktree.holder() is None
    assert authors == {begun.actor} and ran == [begun.actor]
    assert answered(answers, 2)["written_to_files"] is False


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
    assert begun[0].worktree is False
    assert [op.actor for op in ended] == [begun[0].actor]


def test_a_session_takes_the_files_when_it_first_changes_something(
    talk: Talk, workspace: Path
):
    """Connecting is not working. The session is registered from its first
    tool, so the pair panel says who is here — but the flow's files stay the
    human's until the agent changes something, because orientation is never a
    reason somebody cannot check a branch out.

    Once it has taken them, its own edits still reach the files: the lock is
    there so nothing is rewritten *under* the agent, and an edit that agent
    asked for is not something happening under it.
    """
    live = checked_out(talk, "churn", branch="sweep")
    session = talk.held()

    session(hello(name="claude"), tool(1, "context", {}))
    reading = live.worktree.holder()
    answers = session(
        tool(2, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"})
    )
    working = live.worktree.holder()
    session.close()
    afterwards = live.worktree.holder()

    assert reading is None
    assert working is not None and working.label == "claude"
    assert answered(answers, 2)["written_to_files"] is True
    assert "0.94" in source_of(workspace / "churn.flow", "score")
    assert afterwards is None
    assert [op.actor for op in ops_of(live, AgentEnd)] == [working.actor]


def test_a_flow_with_no_files_is_owned_by_nobody_however_much_it_is_written(
    talk: Talk,
):
    """There is nothing to own. A store-only flow has no file plane to be
    rewritten under anyone, and a lock over it would refuse the human a
    checkout to protect files that do not exist."""
    session = talk.held()

    session(
        hello(name="claude"),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "run", {"target": "score"}),
    )
    live = talk.flow("churn")
    working = live.worktree.holder()
    session.close()

    assert working is None
    assert [op.worktree for op in ops_of(live, AgentBegin)] == [False]


def test_the_label_a_configuration_gave_wins_over_the_clients_own_name(talk: Talk):
    """A harness that spawns every MCP server under one generic name is told
    apart by what its configuration says, which is the deliberate answer."""
    session = talk.held(label="pair-1")

    session(hello(name="node"), tool(1, "init-flow", {"name": "churn"}))
    session(tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "s"}))
    live = talk.flow("churn")
    session.close()

    assert [op.label for op in ops_of(live, AgentBegin)] == ["pair-1"]
    assert {version.author for version in slice_of(live, "main").values()} == {
        ops_of(live, AgentBegin)[0].actor
    }


def test_switch_moves_this_session_and_leaves_the_files_alone(
    talk: Talk, workspace: Path
):
    """The daemon's `switch` rebinds a worktree. This one cannot: it sets the
    branch this session works on, and every later tool follows it."""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "fork", {"name": "sweep", "intent": "try a higher lr"}),
        tool(4, "switch", {"branch": "sweep"}),
        tool(
            5, "edit-cell", {"slug": "score", "source": SWEEP_CELL, "intent": "sweep"}
        ),
        tool(6, "context", {}),
        tool(7, "context", {"branch": "main"}),
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


def test_a_session_starts_where_the_files_are_and_switch_leaves_them_there(
    talk: Talk, workspace: Path
):
    """The other half of `switch`: a flow somebody has checked out.

    The session's branch begins as the bound one — the agent lands where the
    files are rather than on whatever `main` holds — and moving it moves
    nothing else. Rebinding the worktree is the daemon's `switch`, and an edit
    to a branch that is not the bound one is owed to no file at all.
    """
    live = checked_out(talk, "churn", branch="sweep")

    answers = talk(
        hello(),
        tool(1, "context", {}),
        tool(2, "switch", {"branch": "main"}),
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
    """`agent_end` names a session, and a session this one never opened is not
    its to close. A begin the daemon refused must leave nothing owed — else the
    hang-up ends the agent working in the files, and takes the worktree lock
    that keeps everyone else's projections off their directory with it.
    """
    live = checked_out(talk, "churn", branch="sweep")
    live.store.commit(
        [AgentBegin(actor="claude-code", label="claude", worktree=True)],
        intent="claude started working",
        actor="claude-code",
    )

    async def refused(params: dict[str, Any]) -> Any:
        raise ServerError("lumlflow dropped `agent.begin`")

    monkeypatch.setitem(talk.api.methods, "agent.begin", refused)
    answers = talk(hello(), tool(1, "context", {}))

    holder = live.worktree.holder()

    assert "agent.begin" in failed(answers, 1)
    assert holder is not None and holder.actor == "claude-code"
    assert ops_of(live, AgentEnd) == []


def test_a_named_branch_that_is_not_there_fails_the_tool_not_the_session(
    talk: Talk,
):
    """A typo is the caller's to fix. The session keeps answering."""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "switch", {"branch": "sweep"}),
        tool(3, "run", {"target": "nowhere"}),
        tool(4, "status", {}),
    )

    refused = failed(answers, 2)

    assert "sweep" in refused and "main" in refused
    assert "nowhere" in failed(answers, 3)
    assert answered(answers, 4)["flows"][0]["flow"] == "churn"


def test_a_tool_missing_an_argument_says_which_one(talk: Talk):
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "edit-cell", {"slug": "score", "intent": "fix it"}),
    )

    assert "`source`" in failed(answers, 2)


def test_resources_serve_the_manifest_the_sources_the_previews_and_the_focus(
    talk: Talk,
):
    """The read-only half: what the flow holds, without invoking anything."""
    answers = talk(
        hello(),
        tool(1, "init-flow", {"name": "churn"}),
        tool(2, "new-cell", {"slug": "score", "source": SCORE_CELL, "intent": "score"}),
        tool(3, "run", {"target": "score"}),
        request(4, "resources/list"),
        request(5, "resources/read", {"uri": "flow://churn/manifest"}),
        request(6, "resources/read", {"uri": "flow://churn/cells/score"}),
        request(7, "resources/read", {"uri": "flow://churn/previews/score.summary"}),
        request(8, "resources/read", {"uri": mcp.FOCUS_URI}),
        request(9, "resources/read", {"uri": "flow://churn/cells/nowhere"}),
    )

    listed = {resource["uri"] for resource in answers[4]["result"]["resources"]}
    manifest = read(answers, 5)
    source = answers[6]["result"]["contents"][0]
    preview = read(answers, 7)
    focus = read(answers, 8)

    assert listed == {
        mcp.FOCUS_URI,
        "flow://churn/manifest",
        "flow://churn/cells/score",
        "flow://churn/previews/score.summary",
    }
    assert [cell["slug"] for cell in manifest["cells"]] == ["score"]
    assert source["mimeType"] == "text/x-python"
    assert "class Score" in source["text"]
    assert preview["kind"] == "metric" and preview["preview"]["blocks"]
    assert (focus["branch"], focus["checked_out"]) == ("main", False)
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
    assert "lane" in tools["run"]["inputSchema"]["properties"]
    assert answers[4]["error"]["code"] == mcp.METHOD_NOT_FOUND


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
    live = talk.hub.init_flow(name)
    live.worktree.checkout(actor="user", force=True)
    live.acceptance.accept_source(
        "score", SCORE_CELL, branch="main", actor="user", intent="scored", fresh=True
    )
    live.store.branches.fork(branch, from_branch="main", actor="user", intent="swept")
    live.worktree.checkout(branch, actor="user", force=True)
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


def test_the_retired_tool_names_still_answer_but_are_never_listed(
    talk: Talk, workspace: Path
):
    """An agent mid-session holds the old list. A fresh one never sees it.

    There have been two renames, so there are two tails. `fork` and `switch`
    are git's spellings; `new-variant` and `use-variant` are the pass between
    them. All four leave `tools/list` and all four keep answering. A rename
    that broke a running session would be a worse failure than the collision it
    fixes. Every argument spelling answers too, because a cached schema names
    one of them.
    """
    make_workspace(workspace, flows=("churn",))
    answers = talk(
        hello(request_id=1),
        request(2, "tools/list"),
        tool(3, "fork", {"name": "sweep", "intent": "the oldest spelling"}),
        tool(4, "switch", {"branch": "sweep"}),
        tool(5, "new-variant", {"name": "second", "intent": "the middle spelling"}),
        tool(6, "use-variant", {"variant": "second"}),
        tool(7, "new-lane", {"name": "third", "intent": "the word"}),
        tool(8, "use-lane", {"lane": "third"}),
    )

    listed = {entry["name"] for entry in answers[2]["result"]["tools"]}
    assert {"new-lane", "use-lane"} <= listed
    assert not {"fork", "switch", "new-variant", "use-variant"} & listed
    assert answered(answers, 3)["branch"] == "sweep"
    assert answered(answers, 4)["branch"] == "sweep"
    assert answered(answers, 5)["branch"] == "second"
    assert answered(answers, 6)["branch"] == "second"
    assert answered(answers, 7)["branch"] == "third"
    assert answered(answers, 8)["branch"] == "third"
