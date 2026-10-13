from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from luml.experiments.tracker import ExperimentTracker
from lumlflow.service import AppService


@pytest.fixture()
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture()
def client(tracker: ExperimentTracker) -> TestClient:
    init_patch = "lumlflow.api.experiments.ExperimentsHandler.__init__"
    with patch(init_patch, lambda self: None):
        app = AppService()

    from lumlflow.api.experiment_groups import groups_handler
    from lumlflow.api.experiments import experiments_handler

    experiments_handler.tracker = tracker
    groups_handler.tracker = tracker
    return TestClient(app)


def test_lumlflow_metadata_is_served_on_experiment_payloads(
    tracker: ExperimentTracker, client: TestClient
) -> None:
    group = tracker.create_group("churn")
    experiment_id = tracker.start_experiment(name="evaluate", group=group.name)
    identity = {
        "flow": "churn",
        "flow_id": "flow-1",
        "path": "/workspace/churn.flow",
        "slug": "evaluate",
        "uid": "cell-1",
        "lane": "main",
        "version_id": "version-1",
        "run_id": "run-1",
    }
    tracker.set_experiment_metadata(experiment_id, {"lumlflow": identity})

    list_response = client.get(
        "/api/groups/experiments", params={"group_ids": group.id}
    )
    detail_response = client.get(f"/api/experiments/{experiment_id}")

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["metadata"] == {"lumlflow": identity}
    assert detail_response.status_code == 200
    assert detail_response.json()["metadata"] == {"lumlflow": identity}


class TestMetricKeyWithSlash:
    def test_metric_key_with_slash(
        self, tracker: ExperimentTracker, client: TestClient
    ) -> None:
        exp_id = tracker.start_experiment(name="test")
        tracker.log_dynamic("train/loss", 0.5, step=1, experiment_id=exp_id)
        tracker.log_dynamic("train/loss", 0.3, step=2, experiment_id=exp_id)
        tracker.end_experiment(exp_id)

        response = client.get(f"/api/experiments/{exp_id}/metrics/train%2Floss")
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "train/loss"
        assert len(data["history"]) == 2

    def test_metric_key_with_multiple_slashes(
        self, tracker: ExperimentTracker, client: TestClient
    ) -> None:
        exp_id = tracker.start_experiment(name="test")
        tracker.log_dynamic("a/b/c/loss", 0.5, step=1, experiment_id=exp_id)
        tracker.end_experiment(exp_id)

        response = client.get(f"/api/experiments/{exp_id}/metrics/a%2Fb%2Fc%2Floss")
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "a/b/c/loss"

    def test_metric_key_without_slash(
        self, tracker: ExperimentTracker, client: TestClient
    ) -> None:
        exp_id = tracker.start_experiment(name="test")
        tracker.log_dynamic("accuracy", 0.9, step=1, experiment_id=exp_id)
        tracker.end_experiment(exp_id)

        response = client.get(f"/api/experiments/{exp_id}/metrics/accuracy")
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "accuracy"
