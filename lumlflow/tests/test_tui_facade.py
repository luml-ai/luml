"""Unit tests for the TUI data-access facade.

The facade wraps the handler layer in a uniform `Result[T]` envelope
(so screens never have to catch `ApplicationError` / `NotFound`) and
retries reads on transient SQLite lock errors. Tests cover:

- the read/mutate paths for each domain (groups, experiments,
  models, annotations);
- the error mapping (NotFound → 404, conflict → 409, validation → 400);
- the transient-lock retry behaviour.

UI behaviour and worker-thread integration are tested separately in
`test_tui_app.py` / future screen tests; here we exercise the facade
synchronously against a seeded tracker.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.annotations import (
    AnnotationKind,
    AnnotationValueType,
    CreateAnnotation,
    UpdateAnnotation,
)
from lumlflow.schemas.experiment_groups import UpdateGroup
from lumlflow.schemas.experiments import UpdateExperiment
from lumlflow.tui.data import (
    DataFacade,
    FacadeError,
    Result,
    _is_transient_lock,
)


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------


class TestResultEnvelope:
    def test_success_factory(self) -> None:
        res: Result[int] = Result.success(42)
        assert res.ok is True
        assert res.value == 42
        assert res.error is None
        assert res.unwrap() == 42

    def test_failure_factory(self) -> None:
        res: Result[int] = Result.failure(404, "Group not found")
        assert res.ok is False
        assert res.value is None
        assert res.error == FacadeError(code=404, message="Group not found")
        assert res.error is not None
        assert res.error.is_not_found is True
        assert res.error.is_conflict is False
        assert res.error.is_validation is False

    def test_unwrap_failure_raises(self) -> None:
        res: Result[int] = Result.failure(500, "boom")
        with pytest.raises(RuntimeError):
            res.unwrap()

    def test_conflict_and_validation_flags(self) -> None:
        conflict: Result[None] = Result.failure(409, "constraint")
        assert conflict.error is not None
        assert conflict.error.is_conflict is True

        bad: Result[None] = Result.failure(400, "invalid")
        assert bad.error is not None
        assert bad.error.is_validation is True


# ---------------------------------------------------------------------------
# Group reads / mutations
# ---------------------------------------------------------------------------


class TestGroups:
    def test_list_groups_empty(self, facade: DataFacade) -> None:
        res = facade.list_groups()
        assert res.ok
        assert res.unwrap().items == []

    def test_list_groups_with_data(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("grp-1", description="first")
        tracker.create_group("grp-2", description="second")
        res = facade.list_groups()
        assert res.ok
        names = {g.name for g in res.unwrap().items}
        assert names == {"grp-1", "grp-2"}

    def test_get_group_not_found_maps_to_404(self, facade: DataFacade) -> None:
        res = facade.get_group("does-not-exist")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404
        assert "not found" in res.error.message.lower()

    def test_update_group_success(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("old-name")
        res = facade.update_group(group.id, UpdateGroup(name="new-name"))
        assert res.ok
        assert res.unwrap().name == "new-name"

    def test_update_group_not_found(self, facade: DataFacade) -> None:
        res = facade.update_group("missing", UpdateGroup(name="x"))
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404

    def test_delete_group_empty(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("to-delete")
        res = facade.delete_group(group.id)
        assert res.ok
        assert facade.list_groups().unwrap().items == []

    def test_delete_group_with_experiments_409(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("linked-grp")
        tracker.start_experiment(name="exp", group=group.name)
        res = facade.delete_group(group.id)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 409
        assert "linked experiments" in res.error.message

    def test_list_group_experiments(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="e1", group=group.name)
        tracker.start_experiment(name="e2", group=group.name)
        res = facade.list_group_experiments(group.id)
        assert res.ok
        assert len(res.unwrap().items) == 2

    def test_list_group_experiments_not_found(self, facade: DataFacade) -> None:
        res = facade.list_group_experiments("missing")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404

    def test_list_groups_experiments_invalid_sort_400(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group1 = tracker.create_group("g1")
        group2 = tracker.create_group("g2")
        tracker.start_experiment(name="x1", group=group1.name)
        tracker.start_experiment(name="x2", group=group2.name)
        res = facade.list_groups_experiments(
            [group1.id, group2.id], sort_by="nonexistent_field"
        )
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 400


# ---------------------------------------------------------------------------
# Experiment reads / mutations
# ---------------------------------------------------------------------------


class TestExperiments:
    def test_get_experiment_success(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="exp-1")
        res = facade.get_experiment(exp_id)
        assert res.ok
        assert res.unwrap().name == "exp-1"

    def test_get_experiment_not_found(self, facade: DataFacade) -> None:
        res = facade.get_experiment("nope")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404

    def test_update_experiment(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="orig")
        res = facade.update_experiment(exp_id, UpdateExperiment(name="renamed"))
        assert res.ok
        assert res.unwrap().name == "renamed"

    def test_delete_experiment(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="to-del")
        res = facade.delete_experiment(exp_id)
        assert res.ok
        # second delete should now 404
        again = facade.delete_experiment(exp_id)
        assert not again.ok
        assert again.error is not None
        assert again.error.code == 404

    def test_metric_history_subsampled(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="m")
        for step in range(50):
            tracker.log_dynamic("loss", float(step), step=step, experiment_id=exp_id)
        res = facade.get_metric_history(exp_id, "loss", max_points=10)
        assert res.ok
        history = res.unwrap()
        assert history.subsampled is True
        assert len(history.history) <= 10

    def test_metric_history_not_found(self, facade: DataFacade) -> None:
        res = facade.get_metric_history("nope", "loss")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404


# ---------------------------------------------------------------------------
# Model reads / mutations
# ---------------------------------------------------------------------------


class TestModels:
    def test_list_empty(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="empty")
        res = facade.list_experiment_models(exp_id)
        assert res.ok
        assert res.unwrap() == []

    def test_get_model_not_found(self, facade: DataFacade) -> None:
        res = facade.get_model("missing")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_eval(
    facade: DataFacade, tracker: ExperimentTracker
) -> tuple[DataFacade, str, str, str]:
    exp_id = tracker.start_experiment(name="ann-test")
    dataset_id = "ds-1"
    eval_id = "eval-1"
    tracker.log_eval_sample(
        eval_id=eval_id,
        dataset_id=dataset_id,
        inputs={"prompt": "hello"},
        experiment_id=exp_id,
    )
    return facade, exp_id, dataset_id, eval_id


@pytest.fixture
def seeded_span(
    facade: DataFacade, tracker: ExperimentTracker
) -> tuple[DataFacade, str, str, str]:
    exp_id = tracker.start_experiment(name="span-test")
    trace_id = "trace-1"
    span_id = "span-1"
    tracker.log_span(
        trace_id=trace_id,
        span_id=span_id,
        name="root",
        start_time_unix_nano=0,
        end_time_unix_nano=1000,
        experiment_id=exp_id,
    )
    return facade, exp_id, trace_id, span_id


class TestAnnotations:
    def test_create_and_list_eval_annotation(
        self, seeded_eval: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, dataset_id, eval_id = seeded_eval
        body = CreateAnnotation(
            name="quality",
            annotation_kind=AnnotationKind.FEEDBACK,
            value_type=AnnotationValueType.BOOL,
            value=True,
            user="alice",
        )
        created = facade.create_eval_annotation(exp_id, dataset_id, eval_id, body)
        assert created.ok
        assert created.unwrap().name == "quality"

        listing = facade.list_eval_annotations(exp_id, dataset_id, eval_id)
        assert listing.ok
        assert len(listing.unwrap()) == 1

    def test_update_eval_annotation(
        self, seeded_eval: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, dataset_id, eval_id = seeded_eval
        created = facade.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="acc",
                annotation_kind=AnnotationKind.FEEDBACK,
                value_type=AnnotationValueType.BOOL,
                value=False,
                user="bob",
            ),
        )
        assert created.ok
        ann = created.unwrap()
        updated = facade.update_eval_annotation(
            exp_id,
            ann.id,
            UpdateAnnotation(value=True, rationale="actually correct"),
        )
        assert updated.ok
        assert updated.unwrap().value is True
        assert updated.unwrap().rationale == "actually correct"

    def test_delete_eval_annotation(
        self, seeded_eval: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, dataset_id, eval_id = seeded_eval
        created = facade.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="acc",
                annotation_kind=AnnotationKind.FEEDBACK,
                value_type=AnnotationValueType.BOOL,
                value=True,
                user="bob",
            ),
        )
        ann_id = created.unwrap().id

        deleted = facade.delete_eval_annotation(exp_id, ann_id)
        assert deleted.ok

        listing = facade.list_eval_annotations(exp_id, dataset_id, eval_id)
        assert listing.ok
        assert listing.unwrap() == []

    def test_create_eval_annotation_invalid_value_type_400(
        self, seeded_eval: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, dataset_id, eval_id = seeded_eval
        body = CreateAnnotation(
            name="q",
            annotation_kind=AnnotationKind.FEEDBACK,
            value_type=AnnotationValueType.STRING,
            value="oops",
            user="alice",
        )
        res = facade.create_eval_annotation(exp_id, dataset_id, eval_id, body)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 400

    def test_create_eval_annotation_experiment_not_found(
        self, facade: DataFacade
    ) -> None:
        res = facade.create_eval_annotation(
            "nope",
            "ds",
            "ev",
            CreateAnnotation(
                name="q",
                annotation_kind=AnnotationKind.FEEDBACK,
                value_type=AnnotationValueType.BOOL,
                value=True,
                user="x",
            ),
        )
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404

    def test_create_and_list_span_annotation(
        self, seeded_span: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, trace_id, span_id = seeded_span
        created = facade.create_span_annotation(
            exp_id,
            trace_id,
            span_id,
            CreateAnnotation(
                name="lat",
                annotation_kind=AnnotationKind.EXPECTATION,
                value_type=AnnotationValueType.INT,
                value=10,
                user="x",
            ),
        )
        assert created.ok

        listing = facade.list_span_annotations(exp_id, trace_id, span_id)
        assert listing.ok
        assert len(listing.unwrap()) == 1
        assert listing.unwrap()[0].name == "lat"

    def test_get_trace_annotation_summary(
        self, seeded_span: tuple[DataFacade, str, str, str]
    ) -> None:
        facade, exp_id, trace_id, _ = seeded_span
        res = facade.get_trace_annotation_summary(exp_id, trace_id)
        assert res.ok


# ---------------------------------------------------------------------------
# Error mapping & retry
# ---------------------------------------------------------------------------


class TestErrorMapping:
    def test_application_error_maps_to_result_failure(
        self, facade: DataFacade
    ) -> None:
        def raises_400() -> None:
            raise ApplicationError("bad input", status_code=400)

        res = facade._mutate(raises_400)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 400
        assert res.error.message == "bad input"

    def test_not_found_maps_to_404(self, facade: DataFacade) -> None:
        def raises_nf() -> None:
            raise NotFound("missing")

        res = facade._mutate(raises_nf)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 404
        assert res.error.message == "missing"

    def test_unexpected_exception_maps_to_500(self, facade: DataFacade) -> None:
        def raises_runtime() -> None:
            raise RuntimeError("boom")

        res = facade._mutate(raises_runtime)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 500
        assert "boom" in res.error.message


class TestTransientLockRetry:
    def test_is_transient_lock_recognises_sqlite_locked(self) -> None:
        assert _is_transient_lock(sqlite3.OperationalError("database is locked"))
        assert _is_transient_lock(sqlite3.OperationalError("database is busy"))
        assert not _is_transient_lock(sqlite3.OperationalError("syntax error"))

    def test_is_transient_lock_recognises_wrapped_message(self) -> None:
        # Even non-sqlite exceptions whose stringification contains the
        # canonical phrase are treated as transient.
        class Wrapped(Exception):
            pass

        assert _is_transient_lock(Wrapped("database is locked while inserting"))
        assert not _is_transient_lock(Wrapped("plain error"))

    def test_read_retries_then_succeeds(
        self, tracker: ExperimentTracker
    ) -> None:
        sleeps: list[float] = []
        facade = DataFacade(
            tracker=tracker,
            retry_attempts=4,
            retry_initial_delay=0.001,
            sleep=lambda d: sleeps.append(d),
        )
        calls = {"n": 0}

        def maybe_locked() -> int:
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return 42

        res = facade._read(maybe_locked)
        assert res.ok
        assert res.unwrap() == 42
        # We slept twice (between attempt 1→2 and 2→3), with backoff doubling.
        assert len(sleeps) == 2
        assert sleeps[0] == pytest.approx(0.001)
        assert sleeps[1] == pytest.approx(0.002)

    def test_read_exhausts_retries(self, tracker: ExperimentTracker) -> None:
        sleeps: list[float] = []
        facade = DataFacade(
            tracker=tracker,
            retry_attempts=3,
            retry_initial_delay=0.001,
            sleep=lambda d: sleeps.append(d),
        )

        def always_locked() -> int:
            raise sqlite3.OperationalError("database is locked")

        res = facade._read(always_locked)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 500
        assert "busy" in res.error.message.lower()
        # Slept after attempts 1 and 2; no sleep after the final attempt.
        assert len(sleeps) == 2

    def test_read_no_retry_on_non_transient(
        self, tracker: ExperimentTracker
    ) -> None:
        sleeps: list[float] = []
        facade = DataFacade(
            tracker=tracker,
            retry_attempts=5,
            retry_initial_delay=0.001,
            sleep=lambda d: sleeps.append(d),
        )

        def raises_value_error() -> int:
            raise ValueError("not a lock")

        res = facade._read(raises_value_error)
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 500
        # Never retried.
        assert sleeps == []

    def test_read_retries_on_application_error_with_transient_cause(
        self, tracker: ExperimentTracker
    ) -> None:
        """Handlers wrap underlying errors in ApplicationError(500).

        When the underlying cause is a transient SQLite lock, the
        facade should still retry rather than surface the wrapped 500.
        """

        sleeps: list[float] = []
        facade = DataFacade(
            tracker=tracker,
            retry_attempts=4,
            retry_initial_delay=0.001,
            sleep=lambda d: sleeps.append(d),
        )
        calls = {"n": 0}

        def maybe_locked() -> int:
            calls["n"] += 1
            if calls["n"] < 2:
                try:
                    raise sqlite3.OperationalError("database is locked")
                except sqlite3.OperationalError as e:
                    raise ApplicationError(str(e), status_code=500) from e
            return 7

        res = facade._read(maybe_locked)
        assert res.ok
        assert res.unwrap() == 7
        assert len(sleeps) == 1


# ---------------------------------------------------------------------------
# Worker offload / async helpers
# ---------------------------------------------------------------------------


def _raise_runtime() -> int:
    raise RuntimeError("nope")


class TestRunInThread:
    async def test_run_in_thread_resolves(self) -> None:
        from lumlflow.tui.data import run_in_thread

        fut = run_in_thread(lambda: 1 + 2)
        result = await fut
        assert result == 3

    async def test_run_in_thread_propagates_exceptions(self) -> None:
        from lumlflow.tui.data import run_in_thread

        fut = run_in_thread(_raise_runtime)
        with pytest.raises(RuntimeError, match="nope"):
            await fut


# ---------------------------------------------------------------------------
# Auth / cloud reachability (mocked)
# ---------------------------------------------------------------------------


class TestAuthCloudErrorMapping:
    def test_set_api_key_validation_failure_maps_401(
        self, facade: DataFacade
    ) -> None:
        with patch.object(
            facade.auth,
            "set_api_key",
            side_effect=ApplicationError("Invalid API key", status_code=401),
        ):
            res = facade.set_api_key("bad")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 401

    def test_set_api_key_unreachable_maps_502(self, facade: DataFacade) -> None:
        with patch.object(
            facade.auth,
            "set_api_key",
            side_effect=ApplicationError("Could not reach LUML platform", 502),
        ):
            res = facade.set_api_key("good")
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 502

    def test_list_organizations_error_maps(self, facade: DataFacade) -> None:
        with patch.object(
            facade.luml,
            "get_luml_organizations",
            side_effect=ApplicationError("not authorized", status_code=401),
        ):
            res = facade.list_organizations()
        assert not res.ok
        assert res.error is not None
        assert res.error.code == 401
