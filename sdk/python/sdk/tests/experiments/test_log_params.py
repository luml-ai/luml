import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from luml.experiments.tracker import ExperimentTracker


class TestLogStatic:
    def test_log_static_float(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("lr", 0.001)

        data = tracker.get_experiment(exp_id)

        assert isinstance(data.static_params["lr"], float)
        assert data.static_params["lr"] == pytest.approx(0.001)

    def test_log_static_int(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("batch_size", 32)

        data = tracker.get_experiment(exp_id)

        assert isinstance(data.static_params["batch_size"], int)
        assert data.static_params["batch_size"] == 32

    def test_log_static_bool(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("use_augmentation", True)

        data = tracker.get_experiment(exp_id)

        assert data.static_params["use_augmentation"] is True

    def test_log_static_str(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("model_arch", "resnet50")

        data = tracker.get_experiment(exp_id)

        assert isinstance(data.static_params["model_arch"], str)
        assert data.static_params["model_arch"] == "resnet50"

    def test_log_static_dict(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("optimizer", {"name": "adam", "weight_decay": 0.01})

        data = tracker.get_experiment(exp_id)

        assert data.static_params["optimizer"] == {"name": "adam", "weight_decay": 0.01}

    def test_log_static_list(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("layers", [64, 128, 256])

        data = tracker.get_experiment(exp_id)

        assert data.static_params["layers"] == [64, 128, 256]

    def test_overwrite_existing_key(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("lr", 0.1)
        tracker.log_static("lr", 0.01)

        data = tracker.get_experiment(exp_id)

        assert data.static_params["lr"] == pytest.approx(0.01)

    def test_multiple_keys_stored_independently(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("lr", 0.001)
        tracker.log_static("epochs", 100)
        tracker.log_static("arch", "vgg16")

        data = tracker.get_experiment(exp_id)

        assert set(data.static_params.keys()) == {"lr", "epochs", "arch"}

    def test_multiple_types_persisted_in_get_experiment(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("lr", 0.001)
        tracker.log_static("arch", "resnet50")
        tracker.log_static("use_amp", True)
        tracker.log_static("cfg", {"dropout": 0.5})

        data = tracker.get_experiment(exp_id)

        assert data.static_params["lr"] == 0.001
        assert data.static_params["arch"] == "resnet50"
        assert data.static_params["use_amp"] is True
        assert data.static_params["cfg"] == {"dropout": 0.5}

    def test_requires_active_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_static("lr", 0.001)

    def test_explicit_experiment_id(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="e1")
        other_id = tracker.start_experiment(name="e2")  # current is now e2

        tracker.log_static("lr", 0.01, experiment_id=exp_id)

        data_exp = tracker.get_experiment(exp_id)
        data_other = tracker.get_experiment(other_id)

        assert "lr" in data_exp.static_params
        assert "lr" not in data_other.static_params


class TestLogDynamic:
    def test_automatic_steps_preserve_all_values(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for value in [1.0, 0.8, 0.5, 0.4]:
            tracker.log_dynamic("loss", value)

        data = tracker.get_experiment(exp_id)

        assert data.dynamic_metrics["loss"] == [
            {"value": 1.0, "step": 0},
            {"value": 0.8, "step": 1},
            {"value": 0.5, "step": 2},
            {"value": 0.4, "step": 3},
        ]

    @pytest.mark.parametrize("step", [0, 5])
    def test_automatic_step_follows_maximum_explicit_step(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        step: int,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 1.0, step=step)
        tracker.log_dynamic("loss", 0.8, step=0)
        tracker.log_dynamic("loss", 0.5)

        data = tracker.get_experiment(exp_id)

        assert data.dynamic_metrics["loss"][-1] == {"value": 0.5, "step": step + 1}

    def test_automatic_steps_are_independent_for_each_metric(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 1.0)
        tracker.log_dynamic("loss", 0.5)
        tracker.log_dynamic("accuracy", 0.8)
        tracker.log_dynamic("accuracy", 0.9)

        data = tracker.get_experiment(exp_id)

        assert data.dynamic_metrics["loss"] == [
            {"value": 1.0, "step": 0},
            {"value": 0.5, "step": 1},
        ]
        assert data.dynamic_metrics["accuracy"] == [
            {"value": 0.8, "step": 0},
            {"value": 0.9, "step": 1},
        ]

    def test_automatic_steps_are_independent_for_each_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        first_id = tracker.start_experiment(name="first")
        second_id = tracker.start_experiment(name="second")
        tracker.log_dynamic("loss", 1.0, experiment_id=first_id)
        tracker.log_dynamic("loss", 0.5, experiment_id=first_id)
        tracker.log_dynamic("loss", 0.8, experiment_id=second_id)

        assert tracker.get_experiment(first_id).dynamic_metrics["loss"] == [
            {"value": 1.0, "step": 0},
            {"value": 0.5, "step": 1},
        ]
        assert tracker.get_experiment(second_id).dynamic_metrics["loss"] == [
            {"value": 0.8, "step": 0},
        ]

    def test_concurrent_automatic_steps_preserve_all_values(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        barrier = threading.Barrier(8)

        def log_metrics(thread_id: int) -> None:
            barrier.wait(timeout=5)
            for i in range(20):
                tracker.log_dynamic("loss", thread_id * 20 + i)

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(log_metrics, range(8)))

        metrics = tracker.get_experiment(exp_id).dynamic_metrics["loss"]

        assert [metric["step"] for metric in metrics] == list(range(160))
        assert sorted(metric["value"] for metric in metrics) == list(range(160))

    def test_value_and_step_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 0.75, step=0)

        history = tracker.get_experiment_metric_history(exp_id, "loss")

        assert len(history) == 1
        assert history[0]["step"] == 0
        assert history[0]["value"] == pytest.approx(0.75)

    def test_multiple_steps_for_same_key(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i, val in enumerate([1.0, 0.8, 0.5, 0.3]):
            tracker.log_dynamic("loss", val, step=i)

        history = tracker.get_experiment_metric_history(exp_id, "loss")

        assert len(history) == 4
        assert [h["step"] for h in history] == [0, 1, 2, 3]
        assert [h["value"] for h in history] == pytest.approx([1.0, 0.8, 0.5, 0.3])

    def test_multiple_metrics_independent(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 0.5, step=0)
        tracker.log_dynamic("acc", 0.9, step=0)
        tracker.log_dynamic("f1", 0.85, step=0)

        data = tracker.get_experiment(exp_id)

        assert set(data.dynamic_metrics.keys()) == {"loss", "acc", "f1"}

    def test_int_value_stored_as_float(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("count", 42, step=0)

        history = tracker.get_experiment_metric_history(exp_id, "count")

        assert history[0]["value"] == 42.0

    def test_multiple_metrics_persisted_in_get_experiment(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 1.0, step=0)
        tracker.log_dynamic("loss", 0.5, step=1)
        tracker.log_dynamic("acc", 0.95, step=0)

        data = tracker.get_experiment(exp_id)

        assert len(data.dynamic_metrics["loss"]) == 2
        assert data.dynamic_metrics["loss"][0] == {"value": 1.0, "step": 0}
        assert data.dynamic_metrics["loss"][1] == {"value": 0.5, "step": 1}
        assert data.dynamic_metrics["acc"][0]["value"] == 0.95

    def test_requires_active_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_dynamic("loss", 0.5, step=0)

    def test_explicit_experiment_id(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="e1")
        other_id = tracker.start_experiment(name="e2")

        tracker.log_dynamic("loss", 0.3, step=0, experiment_id=exp_id)

        data_exp = tracker.get_experiment(exp_id)
        data_other = tracker.get_experiment(other_id)

        assert "loss" in data_exp.dynamic_metrics
        assert "loss" not in data_other.dynamic_metrics

    def test_logged_at_timestamp_is_set(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 0.5, step=0)

        history = tracker.get_experiment_metric_history(exp_id, "loss")

        assert history[0]["logged_at"] is not None
