import dataclasses
from pathlib import Path

import pytest

from luml.experiments.backends._base import Backend
from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationValueType,
    SpanRecord,
    TraceDetails,
)
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker
from tests.experiments.metric_helpers import make_revision2_store

EXP_ID = "exp"
TRACE_ID = "trace"


class DefaultsBackend(SQLiteBackend):
    """A backend that implements only the abstract methods, as custom ones may."""

    get_trace_structure = Backend.get_trace_structure
    get_span = Backend.get_span


def _log_trace(backend: SQLiteBackend) -> None:
    backend.log_span(
        EXP_ID,
        TRACE_ID,
        "root",
        "agent",
        0,
        100,
        kind=1,
        status_code=1,
        attributes={"prompt": "x" * 5000},
        trace_flags=1,
    )
    backend.log_span(
        EXP_ID,
        TRACE_ID,
        "b",
        "tool",
        10,
        60,
        parent_span_id="root",
        status_code=2,
        status_message="timeout",
        attributes={"gen_ai.operation.name": "execute_tool"},
        events=[{"name": "retry", "attributes": {"attempt": 1}}],
        links=[{"trace_id": "other", "span_id": "s"}],
    )
    # Same start as "b": the structure orders ties by span id.
    backend.log_span(
        EXP_ID, TRACE_ID, "a", "llm", 10, 50, parent_span_id="root", kind=3
    )
    backend.log_span(EXP_ID, "other", "s", "other", 0, 1)
    for span_id in ("b", "b", "root"):
        backend.log_span_annotation(
            EXP_ID,
            TRACE_ID,
            span_id,
            "ok",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "user",
        )


def _without_payload(span: SpanRecord) -> SpanRecord:
    return dataclasses.replace(
        span,
        status_message=None,
        attributes=None,
        events=None,
        links=None,
    )


def _sorted(spans: list[SpanRecord]) -> list[SpanRecord]:
    return sorted(spans, key=lambda span: (span.start_time_unix_nano, span.span_id))


@pytest.fixture(params=["revision 4", "revision 2"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> SQLiteBackend:
    store = tmp_path / "store"
    if request.param == "revision 2":
        make_revision2_store(store, EXP_ID)
        backend = SQLiteBackend(str(store), flush_interval=0)
    else:
        backend = SQLiteBackend(str(store), flush_interval=0)
        backend.initialize_experiment(EXP_ID, name=EXP_ID)
    _log_trace(backend)
    expected_revision = 2 if request.param == "revision 2" else 4
    assert backend.get_experiment_ddl_version(EXP_ID) == expected_revision
    return backend


def test_structure_is_the_trace_without_payloads(backend: SQLiteBackend) -> None:
    trace = backend.get_trace(EXP_ID, TRACE_ID)
    assert trace is not None

    structure = backend.get_trace_structure(EXP_ID, TRACE_ID)

    assert structure == TraceDetails(
        trace_id=TRACE_ID,
        spans=[_without_payload(span) for span in _sorted(trace.spans)],
    )
    assert [span.span_id for span in structure.spans] == ["root", "a", "b"]
    assert [span.annotation_count for span in structure.spans] == [1, 0, 2]


@pytest.mark.parametrize("revision", [2, 4])
def test_spans_with_one_start_time_come_back_in_one_order(
    revision: int, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    if revision == 2:
        make_revision2_store(store, EXP_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    if revision == 4:
        backend.initialize_experiment(EXP_ID, name=EXP_ID)
    backend.log_span(EXP_ID, "ties", "root", "root", 0, 100)
    for span_id in ("s4", "s3", "s2", "s1"):
        backend.log_span(
            EXP_ID, "ties", span_id, span_id, 10, 20, parent_span_id="root"
        )
    assert backend.get_experiment_ddl_version(EXP_ID) == revision
    backend.close()
    sqlite = SQLiteBackend(str(store), flush_interval=0)
    defaults = DefaultsBackend(str(store), flush_interval=0)

    expected = ["root", "s1", "s2", "s3", "s4"]
    for reader in (sqlite, defaults):
        trace = reader.get_trace(EXP_ID, "ties")
        structure = reader.get_trace_structure(EXP_ID, "ties")
        assert trace is not None
        assert structure is not None
        assert [span.span_id for span in trace.spans] == expected
        assert [span.span_id for span in structure.spans] == expected
    sqlite.close()
    defaults.close()


def test_span_is_the_span_of_the_trace(backend: SQLiteBackend) -> None:
    trace = backend.get_trace(EXP_ID, TRACE_ID)
    assert trace is not None

    for span in trace.spans:
        assert backend.get_span(EXP_ID, TRACE_ID, span.span_id) == span
    tool = backend.get_span(EXP_ID, TRACE_ID, "b")
    assert tool is not None
    assert tool.status_message == "timeout"
    assert tool.events == [{"name": "retry", "attributes": {"attempt": 1}}]


def test_missing_trace_or_span_is_none(backend: SQLiteBackend) -> None:
    assert backend.get_trace_structure(EXP_ID, "missing") is None
    assert backend.get_span(EXP_ID, "missing", "root") is None
    assert backend.get_span(EXP_ID, TRACE_ID, "missing") is None
    assert backend.get_span(EXP_ID, "other", "root") is None


def test_defaults_of_a_backend_without_overrides_match(tmp_path: Path) -> None:
    store = tmp_path / "store"
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.initialize_experiment(EXP_ID, name=EXP_ID)
    _log_trace(backend)
    backend.close()
    defaults = DefaultsBackend(str(store), flush_interval=0)
    sqlite = SQLiteBackend(str(store), flush_interval=0)

    structure = defaults.get_trace_structure(EXP_ID, TRACE_ID)
    assert structure is not None
    expected = sqlite.get_trace_structure(EXP_ID, TRACE_ID)
    assert expected is not None
    assert _sorted(structure.spans) == expected.spans
    assert defaults.get_span(EXP_ID, TRACE_ID, "b") == sqlite.get_span(
        EXP_ID, TRACE_ID, "b"
    )
    assert defaults.get_trace_structure(EXP_ID, "missing") is None
    assert defaults.get_span(EXP_ID, "missing", "b") is None
    assert defaults.get_span(EXP_ID, TRACE_ID, "missing") is None


def test_tracker_mirrors_the_backend(tmp_path: Path) -> None:
    tracker = ExperimentTracker(f"sqlite://{tmp_path / 'store'}")
    tracker.start_experiment(name=EXP_ID, experiment_id=EXP_ID)
    tracker.log_span(TRACE_ID, "root", "agent", 0, 10, attributes={"a": 1})

    structure = tracker.get_trace_structure(EXP_ID, TRACE_ID)
    span = tracker.get_span(EXP_ID, TRACE_ID, "root")

    assert structure is not None
    assert [s.attributes for s in structure.spans] == [None]
    assert span is not None
    assert span.attributes == {"a": 1}
