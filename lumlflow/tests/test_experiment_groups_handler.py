from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.handlers.experiment_groups import ExperimentGroupsHandler
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.experiment_groups import UpdateGroup


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def handler(tracker: ExperimentTracker) -> ExperimentGroupsHandler:
    return ExperimentGroupsHandler(tracker=tracker)


class TestListGroups:
    def test_empty(self, handler: ExperimentGroupsHandler) -> None:
        result = handler.get_experiment_groups()
        assert result.items == []

    def test_with_data(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        tracker.create_group("grp-1", description="first")
        tracker.create_group("grp-2", description="second")
        result = handler.get_experiment_groups()
        assert len(result.items) == 2
        names = {g.name for g in result.items}
        assert names == {"grp-1", "grp-2"}


class TestGetGroupDetails:
    def test_found(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        group = tracker.create_group("detail-grp", description="test desc")
        details = handler.get_experiment_group_details(group.id)
        assert details.name == "detail-grp"
        assert details.description == "test desc"

    def test_not_found(self, handler: ExperimentGroupsHandler) -> None:
        with pytest.raises(NotFound):
            handler.get_experiment_group_details("nonexistent")


class TestUpdateGroup:
    def test_update_name(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        group = tracker.create_group("old-name")
        updated = handler.update_experiment_group(
            group.id, UpdateGroup(name="new-name")
        )
        assert updated.name == "new-name"

    def test_not_found(self, handler: ExperimentGroupsHandler) -> None:
        with pytest.raises(NotFound):
            handler.update_experiment_group("nonexistent", UpdateGroup(name="x"))


class TestDeleteGroup:
    def test_delete_empty(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        group = tracker.create_group("to-delete")
        handler.delete_experiment_group(group.id)
        result = handler.get_experiment_groups()
        assert len(result.items) == 0

    def test_delete_with_experiments_409(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        group = tracker.create_group("linked-grp")
        tracker.start_experiment(name="exp", group=group.name)
        with pytest.raises(ApplicationError, match="linked experiments"):
            handler.delete_experiment_group(group.id)

    def test_not_found(self, handler: ExperimentGroupsHandler) -> None:
        with pytest.raises(NotFound):
            handler.delete_experiment_group("nonexistent")


class TestListGroupExperiments:
    def test_with_experiments(
        self, tracker: ExperimentTracker, handler: ExperimentGroupsHandler
    ) -> None:
        group = tracker.create_group("exp-grp")
        tracker.start_experiment(name="e1", group=group.name)
        tracker.start_experiment(name="e2", group=group.name)
        result = handler.list_group_experiments(group.id)
        assert len(result.items) == 2

    def test_not_found(self, handler: ExperimentGroupsHandler) -> None:
        with pytest.raises(NotFound):
            handler.list_group_experiments("nonexistent")
