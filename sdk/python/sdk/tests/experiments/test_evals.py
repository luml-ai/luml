import json
import time
from pathlib import Path

import pytest

from luml.experiments.backends.data_types import (
    EvalColumns,
    EvalRecord,
    PaginatedResponse,
)
from luml.experiments.tracker import ExperimentTracker
from tests.conftest import _exp_db


class TestLogEvalSample:
    def test_log_eval_sample_all_fields_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="eval_001",
            dataset_id="ds_1",
            inputs={"prompt": "hello"},
            outputs={"response": "hi"},
            references={"expected": "hi there"},
            scores={"bleu": 0.8},
            metadata={"latency_ms": 42},
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT id, dataset_id, inputs, outputs, refs, scores, metadata FROM evals"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "eval_001"
        assert row[1] == "ds_1"
        assert json.loads(row[2]) == {"prompt": "hello"}
        assert json.loads(row[3]) == {"response": "hi"}
        assert json.loads(row[4]) == {"expected": "hi there"}
        assert json.loads(row[5]) == {"bleu": 0.8}
        assert json.loads(row[6]) == {"latency_ms": 42}

    def test_log_eval_sample_minimal_leaves_optional_null(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="eval_002",
            dataset_id="ds_1",
            inputs={"x": 1},
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT outputs, refs, scores, metadata FROM evals WHERE id = 'eval_002'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert all(col is None for col in row)

    def test_log_eval_sample_requires_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_eval_sample(eval_id="e", dataset_id="d", inputs={"x": 1})


class TestGetExperimentEvals:
    def test_returns_paginated_response(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals(exp_id)

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 1
        assert isinstance(result.items[0], EvalRecord)

    def test_items_have_correct_fields(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"prompt": "hi"},
            outputs={"response": "hello"},
            scores={"bleu": 0.9},
        )

        result = tracker.get_experiment_evals(exp_id)

        rec = result.items[0]
        assert rec.id == "e1"
        assert rec.dataset_id == "ds1"
        assert rec.inputs == {"prompt": "hi"}
        assert rec.outputs == {"response": "hello"}
        assert rec.scores == {"bleu": 0.9}

    def test_filter_by_dataset_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_a", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds_b", inputs={"x": 1})

        result = tracker.get_experiment_evals(exp_id, dataset_id="ds_a")

        assert len(result.items) == 1
        assert result.items[0].id == "e1"

    def test_limit_restricts_page_size(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(5):
            tracker.log_eval_sample(eval_id=f"e{i}", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals(exp_id, limit=3)

        assert len(result.items) == 3

    def test_cursor_pagination(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(4):
            tracker.log_eval_sample(eval_id=f"e{i}", dataset_id="ds1", inputs={"x": 1})

        page1 = tracker.get_experiment_evals(exp_id, limit=2, order="asc")
        assert page1.cursor is not None

        page2 = tracker.get_experiment_evals(
            exp_id, limit=2, order="asc", cursor_str=page1.cursor
        )
        assert len(page2.items) == 2

        ids_p1 = {r.id for r in page1.items}
        ids_p2 = {r.id for r in page2.items}
        assert ids_p1.isdisjoint(ids_p2)

    def test_search_filters_by_eval_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="alpha_1", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="beta_1", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals(exp_id, search="alpha")

        assert len(result.items) == 1
        assert result.items[0].id == "alpha_1"

    def test_empty_experiment_returns_empty_list(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_experiment_evals(exp_id)

        assert result.items == []
        assert result.cursor is None


class TestGetExperimentEvalsAll:
    def test_returns_all_evals(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(6):
            tracker.log_eval_sample(eval_id=f"e{i}", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals_all(exp_id)

        assert isinstance(result, list)
        assert len(result) == 6
        assert all(isinstance(r, EvalRecord) for r in result)

    def test_filter_by_dataset_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_x", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds_y", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e3", dataset_id="ds_x", inputs={"x": 1})

        result = tracker.get_experiment_evals_all(exp_id, dataset_id="ds_x")

        assert len(result) == 2
        assert all(r.dataset_id == "ds_x" for r in result)

    def test_search_filters_by_eval_id_substring(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="train_001", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="test_001", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="train_002", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals_all(exp_id, search="train")

        assert len(result) == 2
        assert all("train" in r.id for r in result)

    def test_empty_experiment_returns_empty_list(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_experiment_evals_all(exp_id)

        assert result == []


class TestGetExperimentEvalColumns:
    def test_returns_eval_columns_type(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"q": "hello"})

        result = tracker.get_experiment_eval_columns(exp_id)

        assert isinstance(result, EvalColumns)

    def test_scores_columns_detected(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"q": "what"},
            scores={"accuracy": 0.9, "f1": 0.8},
        )

        columns = tracker.get_experiment_eval_columns(exp_id)

        assert "accuracy" in columns.scores
        assert "f1" in columns.scores

    def test_inputs_columns_detected(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"prompt": "hi", "context": "doc"},
        )

        columns = tracker.get_experiment_eval_columns(exp_id)

        assert "prompt" in columns.inputs
        assert "context" in columns.inputs

    def test_filter_by_dataset_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds_a",
            inputs={"x": 1},
            scores={"metric_a": 0.5},
        )
        tracker.log_eval_sample(
            eval_id="e2",
            dataset_id="ds_b",
            inputs={"x": 2},
            scores={"metric_b": 0.7},
        )

        columns = tracker.get_experiment_eval_columns(exp_id, dataset_id="ds_a")

        assert "metric_a" in columns.scores
        assert "metric_b" not in columns.scores

    def test_empty_experiment_returns_empty_columns(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        columns = tracker.get_experiment_eval_columns(exp_id)

        assert columns.scores == []
        assert columns.inputs == []


class TestGetExperimentEvalAverageScores:
    def test_average_computed_correctly(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.8}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.6}
        )

        avg = tracker.get_experiment_evals_average_scores(exp_id)

        assert isinstance(avg, dict)
        assert "acc" in avg
        assert avg["acc"] == pytest.approx(0.7)

    def test_multiple_metrics_averaged_independently(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"x": 1},
            scores={"bleu": 0.4, "rouge": 0.6},
        )
        tracker.log_eval_sample(
            eval_id="e2",
            dataset_id="ds1",
            inputs={"x": 2},
            scores={"bleu": 0.6, "rouge": 0.8},
        )

        avg = tracker.get_experiment_evals_average_scores(exp_id)

        assert avg["bleu"] == pytest.approx(0.5)
        assert avg["rouge"] == pytest.approx(0.7)

    def test_filter_by_dataset_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds_a", inputs={"x": 1}, scores={"acc": 1.0}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds_b", inputs={"x": 2}, scores={"acc": 0.0}
        )

        avg = tracker.get_experiment_evals_average_scores(exp_id, dataset_id="ds_a")

        assert avg["acc"] == pytest.approx(1.0)

    def test_empty_experiment_returns_empty_dict(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        avg = tracker.get_experiment_evals_average_scores(exp_id)

        assert avg == {}


class TestGetExperimentEvalDatasetIds:
    def test_returns_distinct_dataset_ids(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_a", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds_b", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e3", dataset_id="ds_a", inputs={"x": 1})

        ids = tracker.get_experiment_eval_dataset_ids(exp_id)

        assert isinstance(ids, list)
        assert set(ids) == {"ds_a", "ds_b"}
        assert len(ids) == 2

    def test_empty_experiment_returns_empty_list(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        ids = tracker.get_experiment_eval_dataset_ids(exp_id)

        assert ids == []

    def test_single_dataset_returned_once(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(3):
            tracker.log_eval_sample(
                eval_id=f"e{i}", dataset_id="only_ds", inputs={"x": 1}
            )

        ids = tracker.get_experiment_eval_dataset_ids(exp_id)

        assert ids == ["only_ds"]

    def test_multiple_evals_same_dataset_deduplicated(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(5):
            tracker.log_eval_sample(eval_id=f"e{i}", dataset_id="ds_x", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e5", dataset_id="ds_y", inputs={"x": 1})

        ids = tracker.get_experiment_eval_dataset_ids(exp_id)

        assert len(ids) == 2
        assert set(ids) == {"ds_x", "ds_y"}


class TestGetEval:
    def test_returns_eval_record_by_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="target",
            dataset_id="ds1",
            inputs={"q": "test"},
            outputs={"a": "answer"},
            scores={"score": 0.9},
        )

        rec = tracker.get_eval(exp_id, "target")

        assert rec is not None
        assert isinstance(rec, EvalRecord)
        assert rec.id == "target"
        assert rec.dataset_id == "ds1"
        assert rec.inputs == {"q": "test"}
        assert rec.outputs == {"a": "answer"}
        assert rec.scores == {"score": 0.9}

    def test_returns_none_for_missing_eval(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        rec = tracker.get_eval(exp_id, "nonexistent")

        assert rec is None

    def test_retrieves_correct_eval_among_multiple(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"val": 1})
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds1", inputs={"val": 2})

        rec = tracker.get_eval(exp_id, "e2")

        assert rec is not None
        assert rec.id == "e2"
        assert rec.inputs == {"val": 2}

    def test_optional_fields_none_when_not_logged(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="minimal", dataset_id="ds1", inputs={"x": 1})

        rec = tracker.get_eval(exp_id, "minimal")

        assert rec is not None
        assert rec.outputs is None
        assert rec.refs is None
        assert rec.scores is None
        assert rec.metadata is None


class TestResolveEvalsSortColumn:
    def test_resolves_scores_key(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"x": 1},
            scores={"accuracy": 0.9},
        )

        col = tracker.resolve_evals_sort_column(exp_id, "accuracy")

        assert col is not None
        assert isinstance(col, str)

    def test_returns_none_for_standard_column(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        col = tracker.resolve_evals_sort_column(exp_id, "created_at")

        assert col is None

    def test_raises_for_unknown_key(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="Invalid sort_by"):
            tracker.resolve_evals_sort_column(exp_id, "nonexistent_key")

    def test_resolves_inputs_key(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"prompt": "hi"},
        )

        col = tracker.resolve_evals_sort_column(exp_id, "prompt")

        assert col is not None


class TestLinkEvalSampleToTrace:
    def test_link_persists_bridge_row(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = time.time_ns()

        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_1", inputs={"x": 1})
        tracker.log_span(
            trace_id="trace_link",
            span_id="span_link",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 100,
        )
        tracker.link_eval_sample_to_trace(
            eval_dataset_id="ds_1",
            eval_id="e1",
            trace_id="trace_link",
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT eval_dataset_id, eval_id, trace_id FROM eval_traces_bridge"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "ds_1"
        assert row[1] == "e1"
        assert row[2] == "trace_link"

    def test_link_requires_existing_eval(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        now = time.time_ns()
        tracker.log_span(
            trace_id="t",
            span_id="s",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1,
        )

        with pytest.raises(ValueError, match="not found"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds", eval_id="missing", trace_id="t"
            )

    def test_link_requires_existing_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_1", inputs={"x": 1})

        with pytest.raises(ValueError, match="not found"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds_1", eval_id="e1", trace_id="missing"
            )

    def test_link_requires_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds", eval_id="e", trace_id="t"
            )
