import json
from pathlib import Path

import pytest

from luml.experiments.backends.data_types import (
    Experiment,
    Group,
    PaginatedResponse,
)
from luml.experiments.tracker import ExperimentTracker
from tests.conftest import _meta_db


def _make_group(tracker: ExperimentTracker, name: str = "g") -> str:
    tracker.start_experiment(group=name)
    return next(g.id for g in tracker.list_groups() if g.name == name)


class TestGroups:
    def test_create_group_persists_to_meta_db(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        group = tracker.create_group("my_group", description="test group")

        assert isinstance(group, Group)
        assert group.name == "my_group"
        assert group.description == "test group"

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT id, name, description FROM experiment_groups WHERE name = ?",
            ("my_group",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == group.id
        assert row[1] == "my_group"
        assert row[2] == "test group"

    def test_create_group_without_description(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        group = tracker.create_group("bare_group")

        assert group.description is None

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT description FROM experiment_groups WHERE name = ?",
            ("bare_group",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] is None

    def test_create_group_idempotent(self, tracker: ExperimentTracker) -> None:
        g1 = tracker.create_group("same_name", description="first")
        g2 = tracker.create_group("same_name", description="second")

        assert g1.id == g2.id

    def test_list_groups_returns_all(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        tracker.create_group("group_a", description="A")
        tracker.create_group("group_b", description="B")

        groups = tracker.list_groups()
        names = {g.name for g in groups}
        assert "group_a" in names
        assert "group_b" in names

        conn = _meta_db(tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM experiment_groups").fetchone()[0]
        conn.close()

        assert count == len(groups)

    def test_list_groups_empty(self, tracker: ExperimentTracker) -> None:
        groups = tracker.list_groups()
        assert isinstance(groups, list)
        assert len(groups) == 0

    def test_create_group_with_tags(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        group = tracker.create_group(
            "tagged_group", description="has tags", tags=["prod", "v2"]
        )

        assert group.tags == ["prod", "v2"]

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT tags FROM experiment_groups WHERE name = ?",
            ("tagged_group",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row[0]) == ["prod", "v2"]

    def test_create_group_without_tags_defaults_empty(
        self, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("no_tags_group")
        assert group.tags == []

    def test_create_group_idempotent_returns_tags(
        self, tracker: ExperimentTracker
    ) -> None:
        g1 = tracker.create_group("tagged_idem", tags=["a", "b"])
        g2 = tracker.create_group("tagged_idem")

        assert g1.id == g2.id
        assert g2.tags == ["a", "b"]

    def test_list_groups_includes_tags(self, tracker: ExperimentTracker) -> None:
        tracker.create_group("g_with_tags", tags=["x"])
        tracker.create_group("g_no_tags")

        groups = tracker.list_groups()
        by_name = {g.name: g for g in groups}
        assert by_name["g_with_tags"].tags == ["x"]
        assert by_name["g_no_tags"].tags == []


class TestGetGroupExperimentsDynamicMetricsKeys:
    def test_returns_empty_for_group_with_no_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.end_experiment(exp_id)
        tracker.delete_experiment(exp_id)

        keys = tracker.get_group_experiments_dynamic_metrics_keys(group_id)

        assert keys == []

    def test_returns_empty_when_no_metrics_logged(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")

        keys = tracker.get_group_experiments_dynamic_metrics_keys(group_id)

        assert keys == []

    def test_returns_sorted_keys_for_single_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_dynamic("val_loss", 0.3, step=0)
        tracker.log_dynamic("train_loss", 0.5, step=0)
        tracker.log_dynamic("accuracy", 0.9, step=0)

        keys = tracker.get_group_experiments_dynamic_metrics_keys(group_id)

        assert keys == sorted(["val_loss", "train_loss", "accuracy"])

    def test_deduplicates_keys_across_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        id1 = tracker.start_experiment(name="exp1", group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_dynamic("loss", 0.5, step=0)
        tracker.log_dynamic("acc", 0.9, step=0)
        tracker.end_experiment(id1)

        tracker.start_experiment(name="exp2", group="g")
        tracker.log_dynamic("loss", 0.4, step=0)
        tracker.log_dynamic("f1", 0.8, step=0)

        keys = tracker.get_group_experiments_dynamic_metrics_keys(group_id)

        assert keys == ["acc", "f1", "loss"]

    def test_skips_experiment_with_missing_db(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        id1 = tracker.start_experiment(name="exp1", group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_dynamic("loss", 0.5, step=0)
        tracker.end_experiment(id1)

        id2 = tracker.start_experiment(name="exp2", group="g")
        tracker.log_dynamic("acc", 0.9, step=0)
        tracker.end_experiment(id2)

        (tmp_path / "experiments" / id2 / "exp.db").unlink()

        keys = tracker.get_group_experiments_dynamic_metrics_keys(group_id)

        assert keys == ["loss"]


class TestGetGroupExperimentsStaticParamsKeys:
    def test_returns_empty_for_group_with_no_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.end_experiment(exp_id)
        tracker.delete_experiment(exp_id)

        keys = tracker.get_group_experiments_static_params_keys(group_id)

        assert keys == []

    def test_returns_empty_when_no_params_logged(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")

        keys = tracker.get_group_experiments_static_params_keys(group_id)

        assert keys == []

    def test_returns_sorted_keys_for_single_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_static("model_type", "resnet")
        tracker.log_static("batch_size", 64)
        tracker.log_static("lr", 0.01)

        keys = tracker.get_group_experiments_static_params_keys(group_id)

        assert keys == sorted(["model_type", "batch_size", "lr"])

    def test_deduplicates_keys_across_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        id1 = tracker.start_experiment(name="exp1", group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_static("lr", 0.01)
        tracker.log_static("batch_size", 32)
        tracker.end_experiment(id1)

        tracker.start_experiment(name="exp2", group="g")
        tracker.log_static("lr", 0.001)
        tracker.log_static("dropout", 0.5)

        keys = tracker.get_group_experiments_static_params_keys(group_id)

        assert keys == ["batch_size", "dropout", "lr"]

    def test_skips_experiment_with_missing_db(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        id1 = tracker.start_experiment(name="exp1", group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.log_static("lr", 0.01)
        tracker.end_experiment(id1)

        id2 = tracker.start_experiment(name="exp2", group="g")
        tracker.log_static("dropout", 0.5)
        tracker.end_experiment(id2)

        (tmp_path / "experiments" / id2 / "exp.db").unlink()

        keys = tracker.get_group_experiments_static_params_keys(group_id)

        assert keys == ["lr"]


class TestListGroupsPagination:
    def test_returns_groups(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="alpha")
        tracker.start_experiment(group="beta")

        result = tracker.list_groups_pagination()

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 2
        assert all(isinstance(g, Group) for g in result.items)

    def test_returns_empty_when_no_groups(self, tracker: ExperimentTracker) -> None:
        result = tracker.list_groups_pagination()

        assert result.items == []
        assert result.cursor is None

    def test_limit_caps_returned_groups(self, tracker: ExperimentTracker) -> None:
        for i in range(4):
            tracker.start_experiment(group=f"group_{i}")

        result = tracker.list_groups_pagination(limit=2)

        assert len(result.items) == 2

    def test_cursor_is_none_when_all_fit(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="alpha")
        tracker.start_experiment(group="beta")

        result = tracker.list_groups_pagination(limit=10)

        assert result.cursor is None

    def test_cursor_enables_next_page(self, tracker: ExperimentTracker) -> None:
        for i in range(3):
            tracker.start_experiment(group=f"group_{i}")

        page1 = tracker.list_groups_pagination(limit=2)
        assert len(page1.items) == 2
        assert page1.cursor is not None

        page2 = tracker.list_groups_pagination(limit=2, cursor_str=page1.cursor)
        assert len(page2.items) == 1
        assert page2.cursor is None
        page1_ids = {g.id for g in page1.items}
        assert all(g.id not in page1_ids for g in page2.items)

    def test_search_filters_by_name(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="nlp_model")
        tracker.start_experiment(group="cv_model")
        tracker.start_experiment(group="nlp_baseline")

        result = tracker.list_groups_pagination(search="nlp")

        names = {g.name for g in result.items}
        assert "nlp_model" in names
        assert "nlp_baseline" in names
        assert "cv_model" not in names

    def test_search_no_match_returns_empty(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="alpha")
        tracker.start_experiment(group="beta")

        result = tracker.list_groups_pagination(search="nonexistent")

        assert result.items == []

    def test_sort_by_name_asc(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="c_group")
        tracker.start_experiment(group="a_group")
        tracker.start_experiment(group="b_group")

        result = tracker.list_groups_pagination(sort_by="name", order="asc")

        names = [g.name for g in result.items]
        assert names == sorted(names)

    def test_sort_by_name_desc(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="c_group")
        tracker.start_experiment(group="a_group")
        tracker.start_experiment(group="b_group")

        result = tracker.list_groups_pagination(sort_by="name", order="desc")

        names = [g.name for g in result.items]
        assert names == sorted(names, reverse=True)

    def test_invalid_sort_by_falls_back_silently(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="alpha")
        tracker.start_experiment(group="beta")

        result = tracker.list_groups_pagination(sort_by="nonexistent_column")

        assert len(result.items) == 2

    def test_invalid_order_falls_back_silently(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.start_experiment(group="alpha")

        result = tracker.list_groups_pagination(order="INVALID")

        assert len(result.items) == 1

    def test_group_fields_populated(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="test_group")

        result = tracker.list_groups_pagination()
        g = result.items[0]

        assert g.id is not None
        assert g.name == "test_group"
        assert g.created_at is not None
        assert g.tags == []

    def test_stale_cursor_is_ignored(self, tracker: ExperimentTracker) -> None:
        for i in range(3):
            tracker.start_experiment(group=f"g{i}")

        page_asc = tracker.list_groups_pagination(sort_by="name", order="asc", limit=2)
        stale_cursor = page_asc.cursor
        assert stale_cursor is not None

        result = tracker.list_groups_pagination(
            sort_by="name", order="desc", limit=2, cursor_str=stale_cursor
        )

        assert len(result.items) == 2
        names = [g.name for g in result.items]
        assert names == sorted(names, reverse=True)


class TestDeleteGroup:
    def test_removes_group_from_listing(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(group="my_group")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "my_group")
        tracker.end_experiment(exp_id)
        tracker.delete_experiment(exp_id)

        tracker.delete_group(group_id)

        assert all(g.id != group_id for g in tracker.list_groups())

    def test_does_not_raise_for_nonexistent_group(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.delete_group("nonexistent-id")

    def test_raises_when_experiments_still_linked(
        self, tracker: ExperimentTracker
    ) -> None:
        import sqlite3

        tracker.start_experiment(name="linked_exp", group="my_group")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "my_group")

        with pytest.raises(sqlite3.IntegrityError):
            tracker.delete_group(group_id)


class TestUpdateGroup:
    def _group_id(self, tracker: ExperimentTracker, name: str = "g") -> str:
        tracker.start_experiment(group=name)
        return next(g.id for g in tracker.list_groups() if g.name == name)

    def test_updates_name(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        result = tracker.update_group(group_id, name="new_name")

        assert result is not None
        assert result.name == "new_name"

    def test_updates_description(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        result = tracker.update_group(group_id, description="my desc")

        assert result is not None
        assert result.description == "my desc"

    def test_updates_tags(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        result = tracker.update_group(group_id, tags=["prod", "v2"])

        assert result is not None
        assert result.tags == ["prod", "v2"]

    def test_updates_all_fields(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        result = tracker.update_group(
            group_id, name="new", description="desc", tags=["x"]
        )

        assert result is not None
        assert result.name == "new"
        assert result.description == "desc"
        assert result.tags == ["x"]

    def test_returns_current_group_when_no_fields_provided(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = self._group_id(tracker, "original")

        result = tracker.update_group(group_id)

        assert result is not None
        assert result.name == "original"

    def test_returns_none_for_nonexistent_group(
        self, tracker: ExperimentTracker
    ) -> None:
        result = tracker.update_group("nonexistent-id", name="x")

        assert result is None

    def test_last_modified_set_after_update(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        result = tracker.update_group(group_id, name="updated")

        assert result is not None
        assert result.last_modified is not None

    def test_update_persists_in_listing(self, tracker: ExperimentTracker) -> None:
        group_id = self._group_id(tracker)

        tracker.update_group(group_id, name="persisted", tags=["saved"])

        groups = tracker.list_groups()
        g = next(g for g in groups if g.id == group_id)
        assert g.name == "persisted"
        assert g.tags == ["saved"]


class TestGetGroup:
    def test_returns_group_by_id(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="my_group")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "my_group")

        result = tracker.get_group(group_id)

        assert isinstance(result, Group)
        assert result.id == group_id
        assert result.name == "my_group"

    def test_returns_none_for_nonexistent_id(self, tracker: ExperimentTracker) -> None:
        result = tracker.get_group("nonexistent-id")

        assert result is None

    def test_returns_empty_tags_when_none_set(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")

        result = tracker.get_group(group_id)

        assert result is not None
        assert result.tags == []

    def test_returns_tags_when_set(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.update_group(group_id, tags=["v1", "prod"])

        result = tracker.get_group(group_id)

        assert result is not None
        assert result.tags == ["v1", "prod"]

    def test_returns_description_when_set(self, tracker: ExperimentTracker) -> None:
        tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.update_group(group_id, description="my desc")

        result = tracker.get_group(group_id)

        assert result is not None
        assert result.description == "my desc"


class TestListGroupExperimentsPagination:
    def test_returns_experiments_in_group(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="exp2", group="g")

        result = tracker.list_group_experiments_pagination(group_id)

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 2
        assert all(isinstance(e, Experiment) for e in result.items)

    def test_returns_empty_for_group_with_no_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(group="g")
        group_id = next(g.id for g in tracker.list_groups() if g.name == "g")
        tracker.end_experiment(exp_id)
        tracker.delete_experiment(exp_id)

        result = tracker.list_group_experiments_pagination(group_id)

        assert result.items == []
        assert result.cursor is None

    def test_limit_caps_returned_items(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="exp2", group="g")
        tracker.start_experiment(name="exp3", group="g")

        result = tracker.list_group_experiments_pagination(group_id, limit=2)

        assert len(result.items) == 2

    def test_cursor_is_none_when_all_items_fit(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="exp2", group="g")

        result = tracker.list_group_experiments_pagination(group_id, limit=10)

        assert result.cursor is None

    def test_cursor_enables_next_page(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker, "g")
        tracker.start_experiment(name="exp2", group="g")
        tracker.start_experiment(name="exp3", group="g")

        page1 = tracker.list_group_experiments_pagination(group_id, limit=2)
        assert len(page1.items) == 2
        assert page1.cursor is not None

        page2 = tracker.list_group_experiments_pagination(
            group_id, limit=2, cursor_str=page1.cursor
        )
        assert len(page2.items) == 1
        assert page2.cursor is None
        page1_ids = {e.id for e in page1.items}
        assert all(e.id not in page1_ids for e in page2.items)

    def test_search_filters_by_name(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="alpha_run", group="g")
        tracker.start_experiment(name="beta_run", group="g")
        tracker.start_experiment(name="alpha_tuned", group="g")

        result = tracker.list_group_experiments_pagination(group_id, search="name LIKE '%alpha%'")

        names = {e.name for e in result.items}
        assert "alpha_run" in names
        assert "alpha_tuned" in names
        assert "beta_run" not in names

    def test_sort_by_name_asc(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="c_exp", group="g")
        tracker.start_experiment(name="a_exp", group="g")
        tracker.start_experiment(name="b_exp", group="g")

        result = tracker.list_group_experiments_pagination(
            group_id, sort_by="name", order="asc"
        )

        names = [e.name for e in result.items]
        assert names == sorted(names)

    def test_sort_by_name_desc(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker)
        tracker.start_experiment(name="c_exp", group="g")
        tracker.start_experiment(name="a_exp", group="g")
        tracker.start_experiment(name="b_exp", group="g")

        result = tracker.list_group_experiments_pagination(
            group_id, sort_by="name", order="desc"
        )

        names = [e.name for e in result.items]
        assert names == sorted(names, reverse=True)

    def test_experiments_isolated_to_group(self, tracker: ExperimentTracker) -> None:
        group_id = _make_group(tracker, "g1")
        other_group_id = _make_group(tracker, "g2")  # noqa: F841
        tracker.start_experiment(name="other_exp", group="g2")

        result = tracker.list_group_experiments_pagination(group_id)

        assert all(e.name != "other_exp" for e in result.items)

    def test_raises_for_invalid_json_sort_column(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = _make_group(tracker)

        with pytest.raises(ValueError):
            tracker.list_group_experiments_pagination(
                group_id, json_sort_column="invalid_column"
            )

    def test_json_sort_column_static_params_does_not_raise(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = _make_group(tracker)
        tracker.log_static("lr", 0.01)
        tracker.start_experiment(name="exp2", group="g")
        tracker.log_static("lr", 0.001)

        result = tracker.list_group_experiments_pagination(
            group_id, sort_by="lr", json_sort_column="static_params", order="asc"
        )

        assert len(result.items) == 2
        assert isinstance(result, PaginatedResponse)
