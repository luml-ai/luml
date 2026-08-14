"""The daemon's web endpoint: one port, three surfaces, two channels.

The app here is the one the daemon builds, over a real hub with real flows, so
what these exercise is the browser's whole path — the tracker it shares the
port with, the flow API it drives, and the socket it watches the workspace
through. Only the daemon process itself is absent; the token it would have
minted is handed in.
"""

import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from luml.experiments.tracker import ExperimentTracker
from lumlflow.flow.daemon import client as daemon_client
from lumlflow.flow.daemon import web, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Streams
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect
from typer.testing import CliRunner

from tests.daemon.helpers import SCORE_CELL, make_workspace, write_cell

TOKEN = "the-workspace-token"
FRAME_LIMIT = 200

CHATTY_CELL = """
class Chatty:
    \"\"\"Says something on its way through.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        print("epoch 1 done")
        return {"summary": {"auc": 0.91}}
"""


@dataclass
class Served:
    """The endpoint, plus the two ways a browser talks to it."""

    http: TestClient
    root: Path
    hub: Hub
    streams: Streams

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        answer = self.http.post(
            web.RPC_PATH,
            json={"method": method, "params": params or {}},
            headers={web.TOKEN_HEADER: TOKEN},
        )
        assert answer.status_code == 200, answer.text
        return answer.json()["result"]

    def watch(self) -> "WebSocketTestSession":
        return self.http.websocket_connect(f"{web.STREAM_PATH}?token={TOKEN}")


@pytest.fixture
def static(tmp_path: Path) -> Path:
    """A build, as the wheel ships one. The API must not be shadowed by it."""
    directory = tmp_path / "static"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text("<html><body>SPA</body></html>")
    (directory / "assets" / "app.js").write_text("console.log('app')")
    return directory


@pytest.fixture
def served(tmp_path: Path, static: Path) -> Iterator[Served]:
    root = make_workspace(tmp_path / "project", flows=("churn", "sweep"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    streams = Streams()
    hub = Hub(root, streams=streams)
    app = web.build_app(hub, Api(hub), streams, token=TOKEN, static=static)
    with TestClient(app) as http:
        try:
            yield Served(http=http, root=root, hub=hub, streams=streams)
        finally:
            # On the app's own loop: the kernels a run started belong to it.
            portal = getattr(http, "portal", None)
            if portal is not None:
                portal.call(hub.close)


@pytest.fixture
def experiments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ExperimentTracker:
    """A store of this test's own, behind the tracker routers the daemon serves.

    The handlers are module-level singletons holding the store they opened at
    import; swapping it here is what keeps a test off the user's real one.
    """
    from lumlflow.api import experiment_groups
    from lumlflow.api import experiments as experiments_api

    tracker = ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")
    monkeypatch.setattr(experiment_groups.groups_handler, "tracker", tracker)
    monkeypatch.setattr(experiments_api.experiments_handler, "tracker", tracker)
    return tracker


def subscribe(socket: WebSocketTestSession, flow: str, cursor: int = 0) -> list[Any]:
    """Watch a flow's journal, and take the catch-up it answers with."""
    socket.send_json({"subscribe": "journal", "flow": flow, "cursor": cursor})
    replayed: list[Any] = []
    for _ in range(FRAME_LIMIT):
        frame = socket.receive_json()
        if frame.get("type") == "caught_up":
            return replayed
        replayed.append(frame)
    raise AssertionError("the catch-up never ended")


def catch_up(socket: WebSocketTestSession, flow: str, cursor: int = 0) -> Any:
    """Watch a flow's journal, and take the marker that ends the catch-up."""
    socket.send_json({"subscribe": "journal", "flow": flow, "cursor": cursor})
    return until(socket, lambda frame: frame.get("type") == "caught_up")


def until(socket: WebSocketTestSession, wanted: Callable[[Any], bool]) -> Any:
    for _ in range(FRAME_LIMIT):
        frame = socket.receive_json()
        if wanted(frame):
            return frame
    raise AssertionError("no frame matched")


def test_the_spa_and_the_tracker_share_the_port_with_the_flow_api(served: Served):
    """Experiments and Workspace are one product on one port — and the static
    fallback answers everything, so it must not answer for the API."""
    assert "SPA" in served.http.get("/flow/churn").text
    assert "console.log" in served.http.get("/assets/app.js").text
    tracker = served.http.get("/api/auth/status")
    assert tracker.headers["content-type"] == "application/json"
    assert served.rpc("ping")["workspace"] == str(served.root)


def test_the_tracker_answers_the_calls_experiments_actually_makes(
    served: Served, experiments: ExperimentTracker
):
    """Not just "some tracker route exists" — the listing the Experiments half
    opens on. A page that got the SPA's index.html here reads its `items` off
    an HTML string, which is the shape of the failure this guards."""
    experiments.create_group("churn")
    experiments.start_experiment(name="first", group="churn")

    listed = served.http.get("/api/groups")

    assert listed.status_code == 200, listed.text
    assert listed.headers["content-type"].startswith("application/json")
    assert [group["name"] for group in listed.json()["items"]] == ["churn"]
    # The SPA is still behind it, for every path the tracker does not claim.
    assert "SPA" in served.http.get("/experiments").text


def test_the_flow_key_gates_the_flow_api_and_not_the_tracker(
    served: Served, experiments: ExperimentTracker
):
    """Experiments was unauthenticated on loopback before it shared this port,
    and sharing a port is not a reason to start asking its callers for a key —
    only the flow API runs the user's code."""
    unkeyed = served.http.get("/api/groups")
    refused = served.http.post(web.RPC_PATH, json={"method": "ping"})

    assert unkeyed.status_code == 200, unkeyed.text
    assert refused.status_code == 401


def test_the_store_the_ui_was_pointed_at_is_the_one_the_tracker_opens(tmp_path: Path):
    """`lumlflow ui --path` sets `BACKEND_STORE_URI` after it has imported the
    daemon, so nothing the daemon imports may open the store on the way in.

    A subprocess because the answer is which modules got imported, and a test
    process has already imported them all.
    """
    store = (tmp_path / "elsewhere").resolve()
    program = (
        "import os, sys\n"
        "os.environ.pop('BACKEND_STORE_URI', None)\n"
        "import lumlflow.cli\n"
        "from lumlflow.flow.daemon import client, workspace\n"
        "from lumlflow.flow.daemon import main as server\n"
        f"os.environ['BACKEND_STORE_URI'] = {str(store)!r}\n"
        "from lumlflow.settings import get_config\n"
        "print(get_config().BACKEND_STORE_URI)\n"
    )

    answered = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )

    assert answered.stdout.strip() == str(store), answered.stderr


def test_the_flow_api_asks_for_the_daemons_token(served: Served):
    """A loopback port is reachable by anything else on the machine, and this
    API runs the user's code."""
    refused = served.http.post(web.RPC_PATH, json={"method": "ping"})
    forged = served.http.post(
        web.RPC_PATH, json={"method": "ping"}, headers={web.TOKEN_HEADER: "guess"}
    )

    assert (refused.status_code, forged.status_code) == (401, 401)
    # The refusal is read by whoever opened the wrong address, so it says what
    # the product says — a key that comes with the address, not a daemon.
    assert "daemon" not in refused.json()["error"]["message"].lower()
    assert "key" in refused.json()["error"]["message"]
    # Closed with a code of its own, not dropped: "you may not" and "the socket
    # went away" are different states with different surfaces.
    with pytest.raises(WebSocketDisconnect) as closed:
        with served.http.websocket_connect(f"{web.STREAM_PATH}?token=guess") as socket:
            socket.receive_json()
    assert closed.value.code == web.WS_UNAUTHORIZED


def test_a_refusal_crosses_as_the_failure_it_was(served: Served):
    answer = served.http.post(
        web.RPC_PATH,
        json={"method": "flow.open", "params": {"flow": "nowhere"}},
        headers={web.TOKEN_HEADER: TOKEN},
    )

    assert answer.status_code == 400
    assert answer.json()["error"]["kind"] == "FlowNotFound"
    assert "`nowhere`" in answer.json()["error"]["message"]

    unknown = served.http.post(
        web.RPC_PATH,
        json={"method": "teleport"},
        headers={web.TOKEN_HEADER: TOKEN},
    )
    assert unknown.status_code == 404


def test_a_subscriber_is_caught_up_and_then_kept_up(served: Served):
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        replayed = subscribe(socket, "churn.flow")
        served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})
        live = until(socket, lambda frame: frame.get("type") == "transaction")

    assert [frame["step"] for frame in replayed] == list(range(1, len(replayed) + 1))
    assert live["flow"] == "churn.flow"
    assert live["step"] > replayed[-1]["step"]
    assert live["transaction"]["intent"] == "added report"


def test_a_reconnect_replays_to_what_a_fresh_load_sees(served: Served):
    """An overnight return and a first open differ in latency, not in state."""
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as first:
        early = subscribe(first, "churn.flow")
    cursor = early[-1]["step"]

    served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})

    with served.watch() as second:
        caught_up = subscribe(second, "churn.flow", cursor=cursor)
    with served.watch() as fresh:
        whole = subscribe(fresh, "churn.flow")

    assert [frame["step"] for frame in caught_up] == [
        step for step in range(cursor + 1, whole[-1]["step"] + 1)
    ]
    assert early + caught_up == whole


def test_two_flows_on_one_daemon_stream_separately(served: Served):
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("flow.open", {"flow": "sweep"})

    with served.watch() as socket:
        subscribe(socket, "churn.flow")
        served.rpc("cells.new", {"flow": "sweep", "slug": "probe"})
        served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})
        frame = until(socket, lambda seen: seen.get("type") == "transaction")

    assert frame["flow"] == "churn.flow"
    assert frame["transaction"]["intent"] == "added report"


def test_a_late_joiner_gets_the_tail_of_a_run_it_missed(served: Served):
    """The card that opens mid-run — or right after one — shows the console it
    was not there for. The chunks were never journaled; the ring held them."""
    write_cell(served.root / "churn.flow", "chatty", CHATTY_CELL)
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        subscribe(socket, "churn.flow")
        outcome = served.rpc("run", {"flow": "churn", "target": "chatty"})
        started = until(socket, lambda frame: frame.get("event") == "started")

        # Only now — the run is over and its chunks are long off the wire.
        socket.send_json(
            {"subscribe": "logs", "flow": "churn", "run_id": started["run_id"]}
        )
        chunk = until(socket, lambda frame: frame.get("channel") == "logs")

    assert outcome["executed"] == ["chatty"]
    assert started["slug"] == "chatty"
    assert "epoch 1 done" in chunk["text"]
    assert chunk["stream"] in ("stdout", "stderr")


def test_a_catch_up_says_what_is_running_as_well_as_where_it_got_to(
    served: Served,
):
    """A run in flight is the other half of where a client stands. Whether a
    late joiner can then reach that console is `test_supervisor.py`'s to say —
    two connections and a blocking run need a daemon of their own."""
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        marker = catch_up(socket, "churn.flow")

    assert marker["running"] == []


def test_a_cursor_the_client_garbled_costs_it_a_replay_not_the_connection(
    served: Served,
):
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        socket.send_json(
            {"subscribe": "journal", "flow": "churn", "cursor": "yesterday"}
        )
        replayed = until(socket, lambda frame: frame.get("type") == "caught_up")
        whole = subscribe(socket, "churn.flow")

    # Read as no cursor at all: over-delivering is what every frame's `step`
    # makes harmless, and it is the catch-up such a client needs anyway.
    assert replayed["step"] == whole[-1]["step"]


def test_a_tab_that_goes_away_stops_being_fanned_out_to(served: Served):
    """A browser closes without a word, and a quiet flow sends nothing to
    notice it by — so the connection's halves have to end each other."""
    with served.watch() as socket:
        subscribe(socket, "churn.flow")
        assert served.streams.watchers == 1

    assert served.streams.watchers == 0


def test_naming_a_flow_that_is_not_here_does_not_end_the_connection(served: Served):
    with served.watch() as socket:
        socket.send_json({"subscribe": "journal", "flow": "nowhere"})
        refused = until(socket, lambda frame: frame.get("type") == "error")

        subscribe(socket, "churn.flow")

    assert "`nowhere`" in refused["message"]


def test_journal_since_answers_the_same_history_over_plain_rpc(served: Served):
    """A client that fell behind the socket replays through the API instead."""
    served.rpc("flow.open", {"flow": "churn"})

    whole = served.rpc("journal.since", {"flow": "churn", "cursor": 0})
    rest = served.rpc("journal.since", {"flow": "churn", "cursor": 1})

    assert [entry["step"] for entry in whole["transactions"]] == list(
        range(1, whole["cursor"] + 1)
    )
    assert rest["transactions"] == whole["transactions"][1:]
    assert whole["flow"] == "churn"


def test_the_address_ui_prints_is_one_this_endpoint_takes(
    served: Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second `lumlflow ui` here points the browser at what is already
    serving — and the SPA is the one caller with no other way to have the
    token, so the address carries it. Which makes it an address only if the
    endpoint accepts what it carries.
    """
    from lumlflow.cli import app

    record = workspace.new_record(
        served.root, port=1, token=TOKEN, web_port=7777, foreground=True
    )
    monkeypatch.setattr(daemon_client, "live_record", lambda root: record)
    monkeypatch.setattr(workspace, "resolve_root", lambda start: served.root)

    result = CliRunner().invoke(app, ["ui", "--no-browser"])
    printed = next(
        word
        for line in result.output.splitlines()
        for word in line.split()
        if word.startswith("http://")
    )

    assert result.exit_code == 0, result.output
    assert printed == f"http://127.0.0.1:7777/?token={TOKEN}"
    assert str(served.root) in result.output
    with served.http.websocket_connect(
        f"{web.STREAM_PATH}?{urlparse(printed).query}"
    ) as socket:
        assert catch_up(socket, "churn.flow")["flow"] == "churn.flow"
