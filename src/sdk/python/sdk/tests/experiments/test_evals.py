import json
import time
from pathlib import Path

import pytest

from luml.experiments.backends.data_types import (
    BatchEvalRecord,
    ColumnField,
    EvalColumns,
    EvalRecord,
    EvalTypedColumns,
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


class TestGetBatchExperimentEvals:
    def _setup_two_experiments(self, tracker: ExperimentTracker) -> tuple[str, str]:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.9}
        )
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds1", inputs={"x": 2})
        exp_b = tracker.start_experiment(name="exp_b")
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.7}
        )
        tracker.log_eval_sample(eval_id="e3", dataset_id="ds1", inputs={"x": 3})
        return exp_a, exp_b

    def test_returns_paginated_response(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b])

        assert isinstance(result, PaginatedResponse)
        assert all(isinstance(item, BatchEvalRecord) for item in result.items)

    def test_items_carry_experiment_id(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b])

        exp_ids = {item.experiment_id for item in result.items}
        assert exp_ids == {exp_a, exp_b}

    def test_groups_same_eval_id_across_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b])

        e1_items = [item for item in result.items if item.id == "e1"]
        assert len(e1_items) == 2
        assert {item.experiment_id for item in e1_items} == {exp_a, exp_b}

    def test_globally_sorted_by_id(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b])

        ids = [item.id for item in result.items]
        assert ids == sorted(ids)

    def test_limit_restricts_unique_ids(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b], limit=2)

        unique_ids = {item.id for item in result.items}
        assert len(unique_ids) <= 2

    def test_cursor_pagination(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        page1 = tracker.get_batch_experiment_evals([exp_a, exp_b], limit=1)

        assert page1.cursor is not None
        ids_page1 = {item.id for item in page1.items}

        page2 = tracker.get_batch_experiment_evals(
            [exp_a, exp_b], limit=10, cursor_str=page1.cursor
        )
        ids_page2 = {item.id for item in page2.items}

        assert ids_page1.isdisjoint(ids_page2)

    def test_cursor_none_when_no_more_pages(self, tracker: ExperimentTracker) -> None:
        exp_a, exp_b = self._setup_two_experiments(tracker)
        result = tracker.get_batch_experiment_evals([exp_a, exp_b], limit=100)

        assert result.cursor is None

    def test_filter_by_dataset_id(self, tracker: ExperimentTracker) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_a", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="e2", dataset_id="ds_b", inputs={"x": 1})

        result = tracker.get_batch_experiment_evals([exp_a], dataset_id="ds_a")

        assert len(result.items) == 1
        assert result.items[0].id == "e1"

    def test_search_filters_by_eval_id(self, tracker: ExperimentTracker) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(eval_id="alpha_1", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="beta_1", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_batch_experiment_evals([exp_a], search="alpha")

        assert len(result.items) == 1
        assert result.items[0].id == "alpha_1"

    def test_empty_when_no_matches(self, tracker: ExperimentTracker) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_batch_experiment_evals([exp_a], dataset_id="nonexistent")

        assert result.items == []
        assert result.cursor is None

    def test_raises_for_missing_experiment(self, tracker: ExperimentTracker) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"x": 1})

        with pytest.raises(ValueError, match="nonexistent-id"):
            tracker.get_batch_experiment_evals([exp_a, "nonexistent-id"])

    def test_skips_experiment_with_no_matching_rows(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(eval_id="a1", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="a2", dataset_id="ds1", inputs={"x": 1})
        exp_b = tracker.start_experiment(name="exp_b")
        tracker.log_eval_sample(eval_id="z1", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="z2", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_batch_experiment_evals([exp_a, exp_b], limit=2)

        assert {item.id for item in result.items} == {"a1", "a2"}
        assert all(item.experiment_id == exp_a for item in result.items)

    def test_preserves_eval_fields(self, tracker: ExperimentTracker) -> None:
        exp_a = tracker.start_experiment(name="exp_a")
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"prompt": "hi"},
            outputs={"answer": "hello"},
            references={"expected": "hello"},
            scores={"bleu": 0.8},
            metadata={"latency_ms": 42},
        )

        result = tracker.get_batch_experiment_evals([exp_a])

        assert len(result.items) == 1
        item = result.items[0]
        assert item.inputs == {"prompt": "hi"}
        assert item.outputs == {"answer": "hello"}
        assert item.refs == {"expected": "hello"}
        assert item.scores == {"bleu": 0.8}
        assert item.metadata == {"latency_ms": 42}


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

    def test_search_filters_samples_before_averaging(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="alpha_1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 1.0}
        )
        tracker.log_eval_sample(
            eval_id="beta_1", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.0}
        )

        avg = tracker.get_experiment_evals_average_scores(exp_id, search="alpha")

        assert avg["acc"] == pytest.approx(1.0)

    def test_filters_applied_before_averaging(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.9}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.3}
        )

        avg = tracker.get_experiment_evals_average_scores(
            exp_id, filters=["scores.acc > 0.5"]
        )

        assert avg["acc"] == pytest.approx(0.9)

    def test_search_and_filters_combined(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="keep_1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.8}
        )
        tracker.log_eval_sample(
            eval_id="keep_2", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.2}
        )
        tracker.log_eval_sample(
            eval_id="drop_1", dataset_id="ds1", inputs={"x": 3}, scores={"acc": 0.9}
        )

        avg = tracker.get_experiment_evals_average_scores(
            exp_id, search="keep", filters=["scores.acc > 0.5"]
        )

        assert avg["acc"] == pytest.approx(0.8)

    def test_filters_matching_nothing_returns_empty_dict(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.4}
        )

        avg = tracker.get_experiment_evals_average_scores(
            exp_id, filters=["scores.acc > 0.9"]
        )

        assert avg == {}

    def test_legacy_backend_signature_still_supported(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        """A backend implementing the pre-search/filters signature must keep
        working when the feature is unused (backward compatibility)."""
        tracker, exp_id = tracker_with_experiment
        captured: dict = {}

        def legacy_backend(
            experiment_id: str, dataset_id: str | None = None
        ) -> dict[str, float]:
            captured["args"] = (experiment_id, dataset_id)
            return {"acc": 1.0}

        tracker.backend.get_evals_average_scores = legacy_backend  # type: ignore[method-assign]

        avg = tracker.get_experiment_evals_average_scores(exp_id, dataset_id="ds1")

        assert avg == {"acc": 1.0}
        assert captured["args"] == (exp_id, "ds1")


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
    def test_get_experiment_evals_populates_trace_ids(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = time.time_ns()
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_1", inputs={"x": 1})
        tracker.log_span(
            trace_id="trace_a",
            span_id="span_a",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 100,
        )
        tracker.log_span(
            trace_id="trace_b",
            span_id="span_b",
            name="op2",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 100,
        )
        tracker.link_eval_sample_to_trace("ds_1", "e1", "trace_a")
        tracker.link_eval_sample_to_trace("ds_1", "e1", "trace_b")

        result = tracker.get_experiment_evals(exp_id)
        assert len(result.items) == 1
        assert set(result.items[0].trace_ids) == {"trace_a", "trace_b"}

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


class TestGetExperimentEvalTypedColumns:
    def test_returns_empty_annotation_fields_for_old_schema(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"x": 1})

        conn = _exp_db(tmp_path, exp_id)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        tracker.backend.pool.close_all()

        result = tracker.get_experiment_eval_typed_columns(exp_id)
        assert result.annotations_feedback == []
        assert result.annotations_expectations == []

    def test_returns_eval_typed_columns_type(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds1", inputs={"q": "hello"})

        result = tracker.get_experiment_eval_typed_columns(exp_id)

        assert isinstance(result, EvalTypedColumns)

    def test_string_type_detected(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"question": "what is AI?"},
            outputs={"answer": "a technology"},
        )

        cols = tracker.get_experiment_eval_typed_columns(exp_id)

        assert any(f.name == "question" and f.type == "string" for f in cols.inputs)
        assert any(f.name == "answer" and f.type == "string" for f in cols.outputs)

    def test_number_type_detected(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"x": 1},
            scores={"accuracy": 0.95, "f1": 0.88},
        )

        cols = tracker.get_experiment_eval_typed_columns(exp_id)

        assert any(f.name == "accuracy" and f.type == "number" for f in cols.scores)
        assert any(f.name == "f1" and f.type == "number" for f in cols.scores)

    def test_column_fields_are_column_field_instances(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"q": "hi"}, scores={"acc": 0.9}
        )

        cols = tracker.get_experiment_eval_typed_columns(exp_id)

        for field in cols.inputs + cols.scores:
            assert isinstance(field, ColumnField)
            assert field.type in {"string", "number", "boolean", "unknown"}

    def test_empty_experiment_returns_empty_typed_columns(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        cols = tracker.get_experiment_eval_typed_columns(exp_id)

        assert cols.inputs == []
        assert cols.scores == []

    def test_filter_by_dataset_id(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds_a", inputs={"x": 1}, scores={"m_a": 0.5}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds_b", inputs={"x": 2}, scores={"m_b": 0.7}
        )

        cols = tracker.get_experiment_eval_typed_columns(exp_id, dataset_id="ds_a")

        assert any(f.name == "m_a" for f in cols.scores)
        assert not any(f.name == "m_b" for f in cols.scores)


class TestGetExperimentEvalsFilter:
    def test_filter_by_output_string(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"q": "hi"}, outputs={"label": "yes"}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds1", inputs={"q": "bye"}, outputs={"label": "no"}
        )

        result = tracker.get_experiment_evals(exp_id, filters=['outputs.label = "yes"'])

        assert len(result.items) == 1
        assert result.items[0].id == "e1"

    def test_filter_by_score_numeric(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.9}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.4}
        )

        result = tracker.get_experiment_evals(exp_id, filters=["scores.acc > 0.7"])

        assert len(result.items) == 1
        assert result.items[0].id == "e1"

    def test_filter_by_id_like(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(eval_id="train_1", dataset_id="ds1", inputs={"x": 1})
        tracker.log_eval_sample(eval_id="test_1", dataset_id="ds1", inputs={"x": 1})

        result = tracker.get_experiment_evals(exp_id, filters=['id LIKE "%train%"'])

        assert len(result.items) == 1
        assert result.items[0].id == "train_1"

    def test_multiple_filters_are_anded(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"x": 1},
            scores={"acc": 0.9},
            outputs={"label": "yes"},
        )
        tracker.log_eval_sample(
            eval_id="e2",
            dataset_id="ds1",
            inputs={"x": 2},
            scores={"acc": 0.9},
            outputs={"label": "no"},
        )

        result = tracker.get_experiment_evals(
            exp_id,
            filters=["scores.acc > 0.7", 'outputs.label = "yes"'],
        )

        assert len(result.items) == 1
        assert result.items[0].id == "e1"

    def test_invalid_filter_raises_value_error(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="Invalid comparator '=>'"):
            tracker.get_experiment_evals(exp_id, filters=["scores.accuracy => 0.5"])

    def test_filter_evals_all_by_score(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"x": 1}, scores={"acc": 0.9}
        )
        tracker.log_eval_sample(
            eval_id="e2", dataset_id="ds1", inputs={"x": 2}, scores={"acc": 0.3}
        )

        result = tracker.get_experiment_evals_all(exp_id, filters=["scores.acc >= 0.8"])

        assert len(result) == 1
        assert result[0].id == "e1"


class TestValidateEvalsFilter:
    def test_valid_filter_returns_none(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        # Should not raise
        tracker.validate_evals_filter('outputs.prediction LIKE "%bert%"')

    def test_none_is_valid(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.validate_evals_filter(None)

    def test_invalid_comparator_raises(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        with pytest.raises(ValueError, match="Invalid comparator '=>'"):
            tracker.validate_evals_filter("scores.accuracy => 0.5")

    def test_invalid_column_raises(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        with pytest.raises(ValueError, match="Invalid field prefix 'unknown_col'"):
            tracker.validate_evals_filter('unknown_col.key = "x"')


class TestBatchEvalsPaginationFull:
    """
    Integration tests for get_batch_experiment_evals pagination.

    3 experiments, 18 unique eval IDs, 30 total records:
      common-01..03    → A + B + C  (3 records each)
      partial-a-01..02 → A + B      (2 records each)
      partial-b-01..02 → B + C      (2 records each)
      partial-c-01..02 → A + C      (2 records each)
      unique-a-01..03  → A only     (1 record each)
      unique-b-01..03  → B only     (1 record each)
      unique-c-01..03  → C only     (1 record each)
    """

    _COMMON = ["common-01", "common-02", "common-03"]
    _PARTIAL_A = ["partial-a-01", "partial-a-02"]  # A + B
    _PARTIAL_B = ["partial-b-01", "partial-b-02"]  # B + C
    _PARTIAL_C = ["partial-c-01", "partial-c-02"]  # A + C
    _UNIQUE_A = ["unique-a-01", "unique-a-02", "unique-a-03"]
    _UNIQUE_B = ["unique-b-01", "unique-b-02", "unique-b-03"]
    _UNIQUE_C = ["unique-c-01", "unique-c-02", "unique-c-03"]
    ALL_IDS = sorted(
        _COMMON
        + _PARTIAL_A
        + _PARTIAL_B
        + _PARTIAL_C
        + _UNIQUE_A
        + _UNIQUE_B
        + _UNIQUE_C
    )

    @pytest.fixture
    def three_exps(self, tracker: ExperimentTracker) -> tuple[str, str, str]:
        ds = "test-ds"
        exp_a = tracker.start_experiment(name="exp_a")
        for eid in self._COMMON + self._PARTIAL_A + self._PARTIAL_C + self._UNIQUE_A:
            tracker.log_eval_sample(
                eval_id=eid, dataset_id=ds, inputs={"exp": "a"}, scores={"v": 1.0}
            )

        exp_b = tracker.start_experiment(name="exp_b")
        for eid in self._COMMON + self._PARTIAL_A + self._PARTIAL_B + self._UNIQUE_B:
            tracker.log_eval_sample(
                eval_id=eid, dataset_id=ds, inputs={"exp": "b"}, scores={"v": 2.0}
            )

        exp_c = tracker.start_experiment(name="exp_c")
        for eid in self._COMMON + self._PARTIAL_B + self._PARTIAL_C + self._UNIQUE_C:
            tracker.log_eval_sample(
                eval_id=eid, dataset_id=ds, inputs={"exp": "c"}, scores={"v": 3.0}
            )

        return exp_a, exp_b, exp_c

    def test_all_ids_covered_no_duplicates(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        exp_a, exp_b, exp_c = three_exps
        seen_ids: list[str] = []
        seen_set: set[str] = set()
        cursor = None
        while True:
            result = tracker.get_batch_experiment_evals(
                [exp_a, exp_b, exp_c], limit=5, cursor_str=cursor
            )
            for r in result.items:
                if r.id not in seen_set:
                    seen_set.add(r.id)
                    seen_ids.append(r.id)
            if result.cursor is None:
                break
            cursor = result.cursor
        assert seen_ids == self.ALL_IDS

    def test_page_boundaries(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        exp_a, exp_b, exp_c = three_exps
        exp_ids = [exp_a, exp_b, exp_c]

        def _unique_ids_in_order(result: PaginatedResponse) -> list[str]:  # type: ignore[type-arg]
            seen: set[str] = set()
            ids: list[str] = []
            for r in result.items:
                if r.id not in seen:
                    seen.add(r.id)
                    ids.append(r.id)
            return ids

        result = tracker.get_batch_experiment_evals(exp_ids, limit=5)
        assert result.cursor is not None
        assert _unique_ids_in_order(result) == self.ALL_IDS[0:5]

        result = tracker.get_batch_experiment_evals(
            exp_ids, limit=5, cursor_str=result.cursor
        )
        assert result.cursor is not None
        assert _unique_ids_in_order(result) == self.ALL_IDS[5:10]

        result = tracker.get_batch_experiment_evals(
            exp_ids, limit=5, cursor_str=result.cursor
        )
        assert result.cursor is not None
        assert _unique_ids_in_order(result) == self.ALL_IDS[10:15]

        result = tracker.get_batch_experiment_evals(
            exp_ids, limit=5, cursor_str=result.cursor
        )
        assert result.cursor is None
        assert _unique_ids_in_order(result) == self.ALL_IDS[15:]

    def test_cursor_is_none_on_last_page(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        exp_a, exp_b, exp_c = three_exps
        exp_ids = [exp_a, exp_b, exp_c]
        cursor = None
        for _ in range(3):
            result = tracker.get_batch_experiment_evals(
                exp_ids, limit=5, cursor_str=cursor
            )
            cursor = result.cursor
        result = tracker.get_batch_experiment_evals(exp_ids, limit=5, cursor_str=cursor)
        assert result.cursor is None
        unique_ids = list(dict.fromkeys(r.id for r in result.items))
        assert len(unique_ids) == 3

    def test_get_batch_evals_first_page_record_counts(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        exp_a, exp_b, exp_c = three_exps
        result = tracker.get_batch_experiment_evals([exp_a, exp_b, exp_c], limit=5)

        assert len(result.items) == 13
        assert result.cursor is not None

        common01 = [r for r in result.items if r.id == "common-01"]
        assert len(common01) == 3
        assert {r.experiment_id for r in common01} == {exp_a, exp_b, exp_c}

        pa01 = [r for r in result.items if r.id == "partial-a-01"]
        assert len(pa01) == 2
        assert {r.experiment_id for r in pa01} == {exp_a, exp_b}

        pairs = [(r.id, r.experiment_id) for r in result.items]
        assert pairs == sorted(pairs)
        assert all(isinstance(r, BatchEvalRecord) for r in result.items)

    def test_full_pagination_30_total_records(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        from collections import Counter

        exp_a, exp_b, exp_c = three_exps
        all_items: list[BatchEvalRecord] = []
        cursor = None

        while True:
            result = tracker.get_batch_experiment_evals(
                [exp_a, exp_b, exp_c], limit=5, cursor_str=cursor
            )
            all_items.extend(result.items)
            if result.cursor is None:
                break
            cursor = result.cursor

        assert len(all_items) == 30

        by_id = Counter(r.id for r in all_items)
        for eid in self._COMMON:
            assert by_id[eid] == 3
        for eid in self._PARTIAL_A + self._PARTIAL_B + self._PARTIAL_C:
            assert by_id[eid] == 2
        for eid in self._UNIQUE_A + self._UNIQUE_B + self._UNIQUE_C:
            assert by_id[eid] == 1

        pairs = [(r.id, r.experiment_id) for r in all_items]
        assert len(pairs) == len(set(pairs))

    def test_pagination_with_dataset_id_filter(
        self, tracker: ExperimentTracker, three_exps: tuple[str, str, str]
    ) -> None:
        exp_a, exp_b, exp_c = three_exps
        tracker.start_experiment(name="exp_a_extra")
        tracker.log_eval_sample(eval_id="other-01", dataset_id="other-ds", inputs={})

        all_items: list[BatchEvalRecord] = []
        cursor = None
        while True:
            result = tracker.get_batch_experiment_evals(
                [exp_a, exp_b, exp_c], limit=5, cursor_str=cursor, dataset_id="test-ds"
            )
            all_items.extend(result.items)
            if result.cursor is None:
                break
            cursor = result.cursor

        unique_ids = list(dict.fromkeys(r.id for r in all_items))
        assert unique_ids == self.ALL_IDS
        assert "other-01" not in unique_ids
