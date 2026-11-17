"""Trace structure (`?payloads=false`) and single span endpoints."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from luml.experiments.tracker import ExperimentTracker

from tests.helpers.metrics import revision2_experiment, serve

TRACE_ID = "tr-1"
PAYLOAD_FIELDS = ("attributes", "events", "links", "status_message")

# Today's default response for the trace `_log_trace` writes, pinned field by field.
DEFAULT_RESPONSE: dict[str, Any] = {
    "trace_id": TRACE_ID,
    "spans": [
        {
            "span_id": "root",
            "parent_span_id": None,
            "name": "run",
            "kind": 1,
            "dfs_span_type": 0,
            "start_time_unix_nano": 1_000,
            "end_time_unix_nano": 9_000,
            "status_code": 1,
            "status_message": None,
            "attributes": {"model": "gpt-4o", "tokens": 512},
            "events": None,
            "links": None,
            "trace_flags": 1,
            "annotation_count": 1,
        },
        {
            "span_id": "tool",
            "parent_span_id": "root",
            "name": "search",
            "kind": 0,
            "dfs_span_type": 0,
            "start_time_unix_nano": 2_000,
            "end_time_unix_nano": 5_000,
            "status_code": 2,
            "status_message": "timeout",
            "attributes": {"query": "weather"},
            "events": [{"name": "retry", "timestamp": 3_000}],
            "links": [{"trace_id": "tr-0", "span_id": "s-0"}],
            "trace_flags": 0,
            "annotation_count": 0,
        },
    ],
    "annotations": {
        "feedback": [{"name": "quality", "total": 1, "counts": {"true": 1}}],
        "expectations": [],
    },
}


def _log_trace(tracker: ExperimentTracker, experiment_id: str) -> None:
    tracker.log_span(
        trace_id=TRACE_ID,
        span_id="tool",
        name="search",
        parent_span_id="root",
        start_time_unix_nano=2_000,
        end_time_unix_nano=5_000,
        status_code=2,
        status_message="timeout",
        attributes={"query": "weather"},
        events=[{"name": "retry", "timestamp": 3_000}],
        links=[{"trace_id": "tr-0", "span_id": "s-0"}],
        experiment_id=experiment_id,
    )
    tracker.log_span(
        trace_id=TRACE_ID,
        span_id="root",
        name="run",
        kind=1,
        start_time_unix_nano=1_000,
        end_time_unix_nano=9_000,
        status_code=1,
        attributes={"model": "gpt-4o", "tokens": 512},
        trace_flags=1,
        experiment_id=experiment_id,
    )


def _annotate(tracker: ExperimentTracker, experiment_id: str) -> None:
    tracker.log_span_annotation(
        trace_id=TRACE_ID,
        span_id="root",
        name="quality",
        annotation_kind="feedback",
        value_type="bool",
        value=True,
        user="tester",
        experiment_id=experiment_id,
    )


@pytest.fixture()
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture()
def experiment_id(tracker: ExperimentTracker) -> str:
    experiment_id = tracker.start_experiment(name="traces")
    _log_trace(tracker, experiment_id)
    _annotate(tracker, experiment_id)
    tracker.end_experiment(experiment_id)
    return experiment_id


def _serve(tracker: ExperimentTracker, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from lumlflow.api.experiments_traces import experiments_handler

    monkeypatch.setattr(experiments_handler, "tracker", tracker)
    return serve(tracker)


@pytest.fixture()
def client(tracker: ExperimentTracker, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return _serve(tracker, monkeypatch)


def _without_payloads(body: dict[str, Any]) -> dict[str, Any]:
    spans = [{**span, **dict.fromkeys(PAYLOAD_FIELDS)} for span in body["spans"]]
    return {**body, "spans": spans}


def _trace_url(experiment_id: str) -> str:
    return f"/api/experiments/{experiment_id}/traces/{TRACE_ID}"


def test_default_response_is_unchanged(client: TestClient, experiment_id: str) -> None:
    default = client.get(_trace_url(experiment_id))
    explicit = client.get(_trace_url(experiment_id), params={"payloads": "true"})

    assert default.status_code == 200
    assert default.json() == DEFAULT_RESPONSE
    assert explicit.content == default.content


def test_structure_response_nulls_only_the_payload_fields(
    client: TestClient, experiment_id: str
) -> None:
    response = client.get(_trace_url(experiment_id), params={"payloads": "false"})

    assert response.status_code == 200
    assert response.json() == _without_payloads(DEFAULT_RESPONSE)


def test_span_equals_the_span_inside_the_default_response(
    client: TestClient, experiment_id: str
) -> None:
    for expected in DEFAULT_RESPONSE["spans"]:
        url = f"{_trace_url(experiment_id)}/spans/{expected['span_id']}"
        response = client.get(url)
        assert response.status_code == 200
        assert response.json() == expected


@pytest.mark.parametrize(
    ("experiment", "trace", "span", "detail"),
    [
        ("missing", TRACE_ID, "root", "Experiment not found"),
        (None, "missing", "root", "Span not found"),
        (None, TRACE_ID, "missing", "Span not found"),
    ],
)
def test_span_not_found(
    client: TestClient,
    experiment_id: str,
    experiment: str | None,
    trace: str,
    span: str,
    detail: str,
) -> None:
    url = f"/api/experiments/{experiment or experiment_id}/traces/{trace}/spans/{span}"
    response = client.get(url)

    assert response.status_code == 404
    assert response.json()["detail"] == detail


@pytest.mark.parametrize("payloads", ["true", "false"])
def test_trace_not_found(client: TestClient, experiment_id: str, payloads: str) -> None:
    params = {"payloads": payloads}
    missing_trace = client.get(
        f"/api/experiments/{experiment_id}/traces/missing", params=params
    )
    missing_experiment = client.get(
        f"/api/experiments/missing/traces/{TRACE_ID}", params=params
    )

    assert missing_trace.status_code == 404
    assert missing_trace.json()["detail"] == "Trace not found"
    assert missing_experiment.status_code == 404
    assert missing_experiment.json()["detail"] == "Experiment not found"


def test_structure_response_leaves_out_a_large_attribute(
    tracker: ExperimentTracker, client: TestClient, experiment_id: str
) -> None:
    big = "x" * 1_000_000
    tracker.log_span(
        trace_id=TRACE_ID,
        span_id="big",
        name="llm",
        parent_span_id="root",
        start_time_unix_nano=6_000,
        end_time_unix_nano=7_000,
        attributes={"prompt": big},
        experiment_id=experiment_id,
    )

    full = client.get(_trace_url(experiment_id))
    structure = client.get(_trace_url(experiment_id), params={"payloads": "false"})
    span = client.get(f"{_trace_url(experiment_id)}/spans/big")

    assert len(full.content) > 1_000_000
    assert len(structure.content) < 2_000
    assert [s["span_id"] for s in structure.json()["spans"]] == [
        "root",
        "tool",
        "big",
    ]
    assert span.json()["attributes"] == {"prompt": big}


def test_revision2_store_serves_structure_and_span(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "experiments"
    experiment_id, db_path = revision2_experiment(store, "loss", [])
    tracker = ExperimentTracker(f"sqlite://{store}")
    _log_trace(tracker, experiment_id)
    _annotate(tracker, experiment_id)
    client = _serve(tracker, monkeypatch)

    default = client.get(_trace_url(experiment_id))
    structure = client.get(_trace_url(experiment_id), params={"payloads": "false"})
    spans = [
        client.get(f"{_trace_url(experiment_id)}/spans/{span_id}").json()
        for span_id in ("root", "tool")
    ]
    tracker.backend.close()

    conn = sqlite3.connect(db_path)
    revision = conn.execute("SELECT MAX(version) FROM exp_schema_migrations").fetchone()
    index = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'spans_structure'"
    ).fetchone()
    conn.close()
    assert revision == (2,)
    assert index is None
    assert default.json() == DEFAULT_RESPONSE
    assert structure.json() == _without_payloads(DEFAULT_RESPONSE)
    assert spans == DEFAULT_RESPONSE["spans"]
