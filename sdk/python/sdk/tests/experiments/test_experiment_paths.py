from functools import partial
from pathlib import Path
from unittest.mock import Mock

import pytest

from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


@pytest.mark.parametrize(
    "experiment_id",
    [
        "",
        ".",
        "..",
        "../escaped",
        "nested/experiment",
        "./experiment",
        "experiment/../other",
        "..\\escaped",
        "nested\\experiment",
        "/absolute",
        "C:\\absolute",
        " experiment",
        "experiment\n",
        "expériment",
        "experiment\x00",
        "a" * 129,
    ],
)
@pytest.mark.parametrize("operation", ["start", "delete"])
def test_tracker_rejects_unsafe_experiment_ids(
    tracker: ExperimentTracker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    experiment_id: str,
    operation: str,
) -> None:
    existing_id = tracker.start_experiment(experiment_id="existing")
    store = tmp_path / "experiments"
    if experiment_id == "/absolute":
        experiment_id = str(tmp_path / "absolute")
    rmtree = Mock()
    monkeypatch.setattr("shutil.rmtree", rmtree)
    action = (
        partial(tracker.start_experiment, experiment_id=experiment_id, group="rejected")
        if operation == "start"
        else partial(tracker.delete_experiment, experiment_id)
    )

    with pytest.raises(ValueError, match="Invalid experiment ID"):
        action()

    rmtree.assert_not_called()
    assert (store / "meta.db").is_file()
    assert (store / existing_id / "exp.db").is_file()
    assert {entry.name for entry in store.iterdir() if entry.is_dir()} == {existing_id}
    assert not (tmp_path / "absolute").exists()
    assert not (tmp_path / "escaped").exists()
    assert [exp.id for exp in tracker.list_experiments()] == [existing_id]
    assert [group.name for group in tracker.list_groups()] == ["default"]
    assert tracker.current_experiment_id == existing_id


@pytest.mark.parametrize("experiment_id", ["a", "Exp_123-test", "a" * 128])
def test_safe_custom_ids_can_be_created_and_deleted(
    tracker: ExperimentTracker, tmp_path: Path, experiment_id: str
) -> None:
    assert tracker.start_experiment(experiment_id=experiment_id) == experiment_id
    assert tracker.get_experiment_record(experiment_id) is not None

    tracker.delete_experiment(experiment_id)

    assert not (tmp_path / "experiments" / experiment_id).exists()
    assert (tmp_path / "experiments" / "meta.db").is_file()
    assert tracker.get_experiment_record(experiment_id) is None


@pytest.mark.parametrize("operation", ["initialize", "delete", "read", "write"])
@pytest.mark.parametrize("target", ["root", "outside"])
def test_experiment_paths_cannot_resolve_to_root_or_outside_store(
    backend: SQLiteBackend,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    target: str,
) -> None:
    destination = backend.base_path if target == "root" else tmp_path / "outside"
    destination.mkdir(exist_ok=True)
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep")
    (backend.base_path / "linked").symlink_to(destination, target_is_directory=True)
    rmtree = Mock()
    monkeypatch.setattr("shutil.rmtree", rmtree)
    action = {
        "initialize": partial(
            backend.initialize_experiment, "linked", group="rejected"
        ),
        "delete": partial(backend.delete_experiment, "linked"),
        "read": partial(backend.get_experiment_data, "linked"),
        "write": partial(backend.log_static, "linked", "key", "value"),
    }[operation]

    with pytest.raises(ValueError, match="Experiment directory"):
        action()

    rmtree.assert_not_called()
    assert sentinel.read_text() == "keep"
    assert backend.meta_db_path.is_file()
    assert not (destination / "exp.db").exists()
    assert backend.list_experiments() == []
    assert backend.list_groups() == []


@pytest.mark.parametrize("operation", ["read", "write"])
def test_existing_outside_experiment_cannot_be_accessed_by_traversal(
    backend: SQLiteBackend, tmp_path: Path, operation: str
) -> None:
    outside = SQLiteBackend(str(tmp_path / "outside"))
    outside.initialize_experiment("experiment")
    action = {
        "read": partial(backend.get_experiment_data, "../outside/experiment"),
        "write": partial(backend.log_static, "../outside/experiment", "key", "value"),
    }[operation]

    with pytest.raises(ValueError, match="Invalid experiment ID"):
        action()

    assert outside.get_experiment_data("experiment").static_params == {}
