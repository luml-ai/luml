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
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from luml.experiments.tracker import ExperimentTracker
from lumlflow.flow.daemon import client as daemon_client
from lumlflow.flow.daemon import daemon_log, queries, web, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.store.models import OutputRecord
from lumlflow.tracker import TrackerProvider
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

NON_FINITE_METRIC_CELL = """
class Diverged:
    produces = {"scores": "asset", "baseline": "asset"}

    def materialize(self, ctx):
        return {
            "scores": {"loss": float("nan"), "auc": 0.00032},
            "baseline": {"auc": 0.75},
        }
"""

TRACKED_EXPERIMENT_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}

    def materialize(self, ctx):
        ctx.tracker.log_metric("rmse", 0.4)
        return {"metrics": ctx.tracker.record}
"""

MODEL_DOWNLOAD_CELL = """
class TrainModel:
    produces = {"model": "model"}

    def materialize(self, ctx):
        return {"model": ("weights", 1)}
"""

UNPERSISTED_CELL = """
class Ephemeral:
    produces = {"value": {"type": "asset", "persist": False}}

    def materialize(self, ctx):
        return {"value": "temporary"}
"""

DOWNLOAD_KINDS_CELL = """
class Downloads:
    produces = {
        "frame": "asset",
        "metric": "asset",
        "evaluation": "asset",
        "plot_png": "asset",
        "plot_json": "asset",
        "note": "asset",
        "checkpoint": "asset",
        "pickle": "asset",
        "report": "asset",
    }

    def materialize(self, ctx):
        import numpy
        import pandas
        import sys
        import types

        class Figure:
            def savefig(self, buffer, **kwargs):
                buffer.write(b"\\x89PNG\\r\\n\\x1a\\n")

        figure_module = types.ModuleType("matplotlib.figure")
        figure_module.Figure = Figure
        sys.modules["matplotlib.figure"] = figure_module

        report = ctx.tempdir() / "report.csv"
        report.write_text("name,score\\na,0.9\\n")
        return {
            "frame": pandas.DataFrame({"score": [0.9]}),
            "metric": {"auc": 0.9},
            "evaluation": [{"name": "a", "score": 0.9}],
            "plot_png": Figure(),
            "plot_json": {"data": [{"x": 1}], "mark": "point"},
            "note": "# report",
            "checkpoint": {"weight": numpy.array([1.0])},
            "pickle": ("opaque", 1),
            "report": report,
        }
"""


@dataclass
class Served:
    """The endpoint, plus the two ways a browser talks to it."""

    http: TestClient
    root: Path
    hub: Hub
    api: Api
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
    hub = Hub(streams=streams)
    api = Api(hub, directory=root)
    app = web.build_app(hub, api, streams, token=TOKEN, static=static)
    with TestClient(app) as http:
        try:
            yield Served(http=http, root=root, hub=hub, api=api, streams=streams)
        finally:
            # On the app's own loop: the kernels a run started belong to it.
            portal = getattr(http, "portal", None)
            if portal is not None:
                portal.call(hub.close)


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


def flow_address(served: Served, name: str = "churn") -> str:
    return str(served.root / f"{name}.flow")


def download(
    served: Served,
    target: str,
    *,
    flow: str | None = None,
    branch: str = "main",
    token: str = TOKEN,
) -> Response:
    return served.http.get(
        web.DOWNLOAD_PATH,
        params={
            "token": token,
            "flow": flow or flow_address(served),
            "branch": branch,
            "target": target,
        },
    )


def test_the_spa_and_the_tracker_share_the_port_with_the_flow_api(served: Served):
    """Experiments and Workspace are one product on one port — and the static
    fallback answers everything, so it must not answer for the API."""
    assert "SPA" in served.http.get("/flow/churn").text
    assert "console.log" in served.http.get("/assets/app.js").text
    tracker = served.http.get("/api/auth/status")
    assert tracker.headers["content-type"] == "application/json"
    assert served.rpc("ping")["workspace"] == str(served.root)


def test_the_tracker_answers_the_calls_experiments_actually_makes(
    served: Served, tracker: TrackerProvider
):
    """Not just "some tracker route exists" — the listing the Experiments half
    opens on. A page that got the SPA's index.html here reads its `items` off
    an HTML string, which is the shape of the failure this guards."""
    tracker.create_group("churn")
    tracker.start_experiment(name="first", group="churn")

    listed = served.http.get("/api/groups")

    assert listed.status_code == 200, listed.text
    assert listed.headers["content-type"].startswith("application/json")
    assert [group["name"] for group in listed.json()["items"]] == ["churn"]
    # The SPA is still behind it, for every path the tracker does not claim.
    assert "SPA" in served.http.get("/experiments").text


def test_the_flow_key_gates_the_flow_api_and_not_the_tracker(
    served: Served, tracker: TrackerProvider
):
    """Experiments was unauthenticated on loopback before it shared this port,
    and sharing a port is not a reason to start asking its callers for a key —
    only the flow API runs the user's code."""
    unkeyed = served.http.get("/api/groups")
    refused = served.http.post(web.RPC_PATH, json={"method": "ping"})

    assert unkeyed.status_code == 200, unkeyed.text
    assert refused.status_code == 401


def test_every_tracker_router_uses_the_per_test_store(
    served: Served, tracker: TrackerProvider
) -> None:
    from lumlflow.api import (
        annotations,
        experiment_groups,
        experiments,
        experiments_evals,
        experiments_traces,
        luml,
        models,
    )

    handlers = (
        annotations.annotations_handler,
        experiment_groups.groups_handler,
        experiments.experiments_handler,
        experiments.models_handler,
        experiments_evals.experiments_handler,
        experiments_traces.experiments_handler,
        luml.luml_handler,
        luml.artifact_handler,
        models.models_handler,
    )
    assert all(handler.tracker is tracker for handler in handlers)

    tracker.create_group("isolated")
    experiment_id = tracker.start_experiment(name="only-here", group="isolated")
    paths = (
        "/api/groups",
        f"/api/experiments/{experiment_id}",
        f"/api/experiments/{experiment_id}/evals/dataset-ids",
        f"/api/experiments/{experiment_id}/traces/columns",
        f"/api/experiments/{experiment_id}/models",
        f"/api/experiments/{experiment_id}/evals/data/sample/annotations",
    )

    for path in paths:
        response = served.http.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"


def test_delete_through_the_experiments_api_fires_the_provider_hook(
    served: Served, tracker: TrackerProvider
) -> None:
    experiment_id = tracker.start_experiment(name="remove-me", group="isolated")
    deleted: list[str] = []

    unsubscribe = tracker.on_experiment_deleted(deleted.append)
    try:
        response = served.http.delete(f"/api/experiments/{experiment_id}")
    finally:
        unsubscribe()

    assert response.status_code == 204, response.text
    assert deleted == [experiment_id]
    assert tracker.get_experiment_record(experiment_id) is None


def test_deleting_a_flow_experiment_pushes_state_without_moving_the_cursor(
    served: Served, tracker: TrackerProvider
) -> None:
    write_cell(served.root / "churn.flow", "evaluate", TRACKED_EXPERIMENT_CELL)
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("run", {"flow": "churn", "target": "evaluate"})
    session = served.hub.session("churn")
    branch_id = session.store.branches.get("main").branch_id
    versions = session.store.index.slice_versions(branch_id)
    uid = next(uid for uid, version in versions.items() if version.slug == "evaluate")
    mat_id = session.store.index.baselines(branch_id)[uid]
    mat = session.store.index.materialization(mat_id)
    assert mat is not None
    ref = mat.outputs["metrics"].tracker_ref
    assert ref is not None
    cursor = session.store.next_step - 1
    journal_before = list(session.store.journal.replay())

    with served.watch() as socket:
        assert subscribe(socket, flow_address(served), cursor=cursor) == []
        assert queries.experiment_state(session, ref).state == "ok"

        response = served.http.delete(f"/api/experiments/{ref.experiment_id}")
        frame = until(socket, lambda candidate: candidate.get("type") == "state")

    assert response.status_code == 204, response.text
    assert frame == {
        "channel": "journal",
        "type": "state",
        "state": "experiment_removed",
        "flow": flow_address(served),
        "lane": "main",
        "cell": "evaluate",
        "step": cursor,
    }
    assert queries.experiment_state(session, ref).state == "missing"
    assert list(session.store.journal.replay()) == journal_before

    with served.watch() as reconnected:
        replayed = subscribe(reconnected, flow_address(served), cursor=cursor)
    assert all(candidate.get("type") != "state" for candidate in replayed)

    served.rpc("run", {"flow": "churn", "target": "evaluate"})
    replacement_id = session.store.index.baselines(branch_id)[uid]
    replacement = session.store.index.materialization(replacement_id)
    assert replacement is not None
    replacement_ref = replacement.outputs["metrics"].tracker_ref
    assert replacement_ref is not None
    assert queries.experiment_state(session, replacement_ref).state == "ok"
    external = ExperimentTracker(f"sqlite://{tracker.store_path}")
    external.delete_experiment(replacement_ref.experiment_id)
    assert queries.experiment_state(session, replacement_ref).state == "ok"

    reconnect_cursor = session.store.next_step - 1
    with served.watch() as reconnected:
        replayed = subscribe(reconnected, flow_address(served), cursor=reconnect_cursor)
    assert all(candidate.get("type") != "state" for candidate in replayed)
    assert queries.experiment_state(session, replacement_ref).state == "missing"


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
        "os.environ.pop('LUML_BACKEND_STORE_URI', None)\n"
        "import lumlflow.cli\n"
        "from lumlflow.flow.daemon import client, workspace\n"
        "from lumlflow.flow.daemon import main as server\n"
        f"os.environ['BACKEND_STORE_URI'] = {str(store)!r}\n"
        "from lumlflow.settings import get_config, get_tracker\n"
        "print(get_config().BACKEND_STORE_URI)\n"
        "print(get_tracker().store_path)\n"
    )

    answered = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )

    assert answered.stdout.splitlines() == [str(store), str(store)], answered.stderr


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


def test_a_bad_numeric_parameter_is_a_json_refusal(
    served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    answer = served.http.post(
        web.RPC_PATH,
        json={"method": "rewind", "params": {"flow": "churn", "to_step": "abc"}},
        headers={web.TOKEN_HEADER: TOKEN, "Origin": "http://workbench.test"},
    )

    assert answer.status_code == 400
    assert answer.headers["access-control-allow-origin"] == "*"
    assert answer.json() == {
        "error": {"kind": "FlowError", "message": "`to_step` must be an integer"}
    }
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_an_unexpected_failure_is_json_and_logs_its_traceback(
    served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fail(_params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("the store failed")

    daemon_log.configure()
    try:
        served.api.methods["test.fail"] = fail
        answer = served.http.post(
            web.RPC_PATH,
            json={"method": "test.fail"},
            headers={web.TOKEN_HEADER: TOKEN, "Origin": "http://workbench.test"},
        )
    finally:
        daemon_log.close()

    assert answer.status_code == 500
    assert answer.headers["access-control-allow-origin"] == "*"
    assert answer.json() == {"error": {"message": "the store failed"}}
    assert "Traceback" not in answer.text
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    logged = workspace.log_path().read_text("utf-8")
    assert "Traceback" in logged
    assert "RuntimeError: the store failed" in logged


def test_http_refuses_asset_download_without_writing_anywhere(
    served: Served, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("run", {"flow": "churn", "target": "score"})
    daemon_cwd = tmp_path / "daemon-cwd"
    daemon_cwd.mkdir()
    monkeypatch.chdir(daemon_cwd)
    destination = tmp_path / "downloaded.summary"
    headers = {web.TOKEN_HEADER: TOKEN}

    with_to = served.http.post(
        web.RPC_PATH,
        json={
            "method": "asset.download",
            "params": {
                "flow": "churn",
                "target": "score.summary",
                "to": str(destination),
            },
        },
        headers=headers,
    )
    without_to = served.http.post(
        web.RPC_PATH,
        json={
            "method": "asset.download",
            "params": {"flow": "churn", "target": "score.summary"},
        },
        headers=headers,
    )

    for answer in (with_to, without_to):
        assert answer.status_code == 400
        assert answer.json()["error"]["kind"] == "FlowError"
        assert "asset.download" in answer.json()["error"]["message"]
    assert not destination.exists()
    assert list(daemon_cwd.iterdir()) == []


def test_asset_download_route_requires_the_token_and_an_absolute_flow_path(
    served: Served,
) -> None:
    missing_key = served.http.get(
        web.DOWNLOAD_PATH,
        params={
            "flow": flow_address(served),
            "branch": "main",
            "target": "score.summary",
        },
    )
    wrong_key = download(served, "score.summary", token="guess")
    bare_name = download(served, "score.summary", flow="churn")
    unknown_path = download(
        served,
        "score.summary",
        flow=str(served.root / "missing.flow"),
    )

    assert (missing_key.status_code, wrong_key.status_code) == (401, 401)
    assert bare_name.status_code == 400
    assert "path" in bare_name.json()["error"]["message"]
    assert unknown_path.status_code == 404
    assert "missing.flow" in unknown_path.json()["error"]["message"]


def test_asset_download_route_refuses_missing_values_lanes_and_experiments(
    served: Served,
) -> None:
    write_cell(served.root / "churn.flow", "evaluate", TRACKED_EXPERIMENT_CELL)
    write_cell(served.root / "churn.flow", "ephemeral", UNPERSISTED_CELL)
    served.rpc("flow.open", {"flow": "churn"})

    unstored = download(served, "score.summary")
    assert unstored.status_code == 404
    assert "nothing is stored" in unstored.json()["error"]["message"]

    served.rpc("run", {"flow": "churn", "target": "score"})
    unknown_lane = download(served, "score.summary", branch="missing")
    assert unknown_lane.status_code == 404
    assert "missing" in unknown_lane.json()["error"]["message"]

    served.rpc("run", {"flow": "churn", "target": "ephemeral"})
    unpersisted = download(served, "ephemeral.value")
    assert unpersisted.status_code == 404
    assert "not to persist" in unpersisted.json()["error"]["message"]

    served.rpc("run", {"flow": "churn", "target": "evaluate"})
    experiment = download(served, "evaluate.metrics")
    assert experiment.status_code == 404
    assert "experiment" in experiment.json()["error"]["message"]


def test_asset_download_route_streams_each_kind_under_its_download_name(
    served: Served,
) -> None:
    write_cell(served.root / "churn.flow", "downloads", DOWNLOAD_KINDS_CELL)
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("run", {"flow": "churn", "target": "downloads"})
    paths_before = {path.relative_to(served.root) for path in served.root.rglob("*")}

    expected_names = {
        "frame": "downloads.frame.arrow",
        "metric": "downloads.metric.json",
        "evaluation": "downloads.evaluation.json",
        "plot_png": "downloads.plot_png.png",
        "plot_json": "downloads.plot_json.json",
        "note": "downloads.note.md",
        "checkpoint": "downloads.checkpoint.pkl",
        "pickle": "downloads.pickle.pkl",
        "report": "report.csv",
    }
    responses = {
        output: download(served, f"downloads.{output}") for output in expected_names
    }

    for output, expected_name in expected_names.items():
        response = responses[output]
        assert response.status_code == 200, response.text
        assert response.headers["content-disposition"].startswith("attachment")
        assert expected_name in response.headers["content-disposition"]
    assert responses["plot_png"].content.startswith(b"\x89PNG\r\n\x1a\n")
    assert responses["plot_json"].json()["mark"] == "point"
    assert responses["report"].text == "name,score\na,0.9\n"
    paths_after = {path.relative_to(served.root) for path in served.root.rglob("*")}
    assert paths_after == paths_before


def test_a_model_download_is_an_attachment_and_writes_nothing_to_the_workspace(
    served: Served,
) -> None:
    write_cell(served.root / "churn.flow", "train_model", MODEL_DOWNLOAD_CELL)
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("run", {"flow": "churn", "target": "train_model"})
    paths_before = {path.relative_to(served.root) for path in served.root.rglob("*")}

    response = download(served, "train_model.model")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert "train_model.model.pkl" in response.headers["content-disposition"]
    paths_after = {path.relative_to(served.root) for path in served.root.rglob("*")}
    assert paths_after == paths_before


def test_a_file_download_without_a_recorded_name_uses_the_output_name(
    tmp_path: Path,
) -> None:
    stored = tmp_path / "value"
    stored.write_bytes(b"report")
    record = OutputRecord(
        content_hash="hash",
        kind="file",
        kind_source="matcher",
        size=6,
        value_ref="value",
    )

    assert web._download_name("report", "csv", record, stored) == "report.csv"


def test_a_non_finite_metric_preview_crosses_the_http_door_as_a_string(
    served: Served,
) -> None:
    write_cell(served.root / "churn.flow", "diverged", NON_FINITE_METRIC_CELL)
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("run", {"flow": "churn", "target": "diverged"})

    answer = served.http.post(
        web.RPC_PATH,
        json={
            "method": "asset.preview",
            "params": {"flow": "churn", "target": "diverged.scores"},
        },
        headers={web.TOKEN_HEADER: TOKEN},
    )

    assert answer.status_code == 200, answer.text
    entries = answer.json()["result"]["preview"]["blocks"][0]["entries"]
    assert entries == {"auc": 0.00032, "loss": "nan"}

    absent = served.http.post(
        web.RPC_PATH,
        json={
            "method": "asset.preview",
            "params": {"flow": "churn", "target": "diverged.baseline"},
        },
        headers={web.TOKEN_HEADER: TOKEN},
    )

    assert absent.status_code == 200, absent.text
    absent_entries = absent.json()["result"]["preview"]["blocks"][0]["entries"]
    assert absent_entries == {"auc": 0.75}


def test_a_subscriber_is_caught_up_and_then_kept_up(served: Served):
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        replayed = subscribe(socket, flow_address(served))
        served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})
        live = until(socket, lambda frame: frame.get("type") == "transaction")

    assert [frame["step"] for frame in replayed] == list(range(1, len(replayed) + 1))
    assert live["flow"] == flow_address(served)
    assert live["step"] > replayed[-1]["step"]
    assert live["transaction"]["intent"] == "added report"


def test_a_reconnect_replays_to_what_a_fresh_load_sees(served: Served):
    """An overnight return and a first open differ in latency, not in state."""
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as first:
        early = subscribe(first, flow_address(served))
    cursor = early[-1]["step"]

    served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})

    with served.watch() as second:
        caught_up = subscribe(second, flow_address(served), cursor=cursor)
    with served.watch() as fresh:
        whole = subscribe(fresh, flow_address(served))

    assert [frame["step"] for frame in caught_up] == [
        step for step in range(cursor + 1, whole[-1]["step"] + 1)
    ]
    assert early + caught_up == whole


def test_two_flows_on_one_daemon_stream_separately(served: Served):
    served.rpc("flow.open", {"flow": "churn"})
    served.rpc("flow.open", {"flow": "sweep"})

    with served.watch() as socket:
        subscribe(socket, flow_address(served))
        served.rpc("cells.new", {"flow": "sweep", "slug": "probe"})
        served.rpc("cells.new", {"flow": "churn", "slug": "report", "after": "score"})
        frame = until(socket, lambda seen: seen.get("type") == "transaction")

    assert frame["flow"] == flow_address(served)
    assert frame["transaction"]["intent"] == "added report"


def test_a_late_joiner_gets_the_tail_of_a_run_it_missed(served: Served):
    """The card that opens mid-run — or right after one — shows the console it
    was not there for. The chunks were never journaled; the ring held them."""
    write_cell(served.root / "churn.flow", "chatty", CHATTY_CELL)
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        subscribe(socket, flow_address(served))
        outcome = served.rpc("run", {"flow": "churn", "target": "chatty"})
        started = until(socket, lambda frame: frame.get("event") == "started")

        # Only now — the run is over and its chunks are long off the wire.
        socket.send_json(
            {
                "subscribe": "logs",
                "flow": flow_address(served),
                "run_id": started["run_id"],
            }
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
        marker = catch_up(socket, flow_address(served))

    assert marker["running"] == []


def test_a_cursor_the_client_garbled_costs_it_a_replay_not_the_connection(
    served: Served,
):
    served.rpc("flow.open", {"flow": "churn"})

    with served.watch() as socket:
        socket.send_json(
            {
                "subscribe": "journal",
                "flow": flow_address(served),
                "cursor": "yesterday",
            }
        )
        replayed = until(socket, lambda frame: frame.get("type") == "caught_up")
        whole = subscribe(socket, flow_address(served))

    # Read as no cursor at all: over-delivering is what every frame's `step`
    # makes harmless, and it is the catch-up such a client needs anyway.
    assert replayed["step"] == whole[-1]["step"]


def test_a_tab_that_goes_away_stops_being_fanned_out_to(served: Served):
    """A browser closes without a word, and a quiet flow sends nothing to
    notice it by — so the connection's halves have to end each other."""
    with served.watch() as socket:
        subscribe(socket, flow_address(served))
        assert served.streams.watchers == 1

    assert served.streams.watchers == 0


def test_naming_a_flow_that_is_not_here_does_not_end_the_connection(served: Served):
    with served.watch() as socket:
        socket.send_json({"subscribe": "journal", "flow": "nowhere"})
        refused = until(socket, lambda frame: frame.get("type") == "error")

        subscribe(socket, flow_address(served))

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
    assert whole["path"] == flow_address(served)


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
        instance_id="served",
        port=1,
        token=TOKEN,
        web_host="127.0.0.1",
        web_port=7777,
        tracker_store="/tmp/experiments",
    )
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.setenv("BACKEND_STORE_URI", record.tracker_store)
    monkeypatch.setattr(daemon_client, "discover", lambda: record)

    result = CliRunner().invoke(app, ["ui", "--no-browser"])
    printed = next(
        word
        for line in result.output.splitlines()
        for word in line.split()
        if word.startswith("http://")
    )

    assert result.exit_code == 0, result.output
    parsed = urlparse(printed)
    assert parsed.path == "/flow"
    assert parse_qs(parsed.query) == {
        "token": [TOKEN],
        "directory": [str(Path.cwd())],
        "log": [str(workspace.log_path())],
    }
    with served.http.websocket_connect(
        f"{web.STREAM_PATH}?{urlparse(printed).query}"
    ) as socket:
        assert catch_up(socket, flow_address(served))["flow"] == flow_address(served)
