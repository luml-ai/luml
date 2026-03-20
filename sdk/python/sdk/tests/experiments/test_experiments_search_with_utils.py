# flake8: noqa: E501
from pathlib import Path

import pytest

from luml.experiments.backends._exceptions import LumlFilterError
from luml.experiments.backends._search_utils import SearchExperimentsUtils
from luml.experiments.backends.sqlite import SQLiteBackend

class TestValidateFilterString:
    def test_valid_name_like(self) -> None:
        SearchExperimentsUtils.validate_filter_string(
            'name LIKE "%bert%"'
        )  # no exception

    def test_valid_none(self) -> None:
        SearchExperimentsUtils.validate_filter_string(None)  # no exception

    def test_valid_empty(self) -> None:
        SearchExperimentsUtils.validate_filter_string("")  # no exception

    def test_valid_combined(self) -> None:
        SearchExperimentsUtils.validate_filter_string(
            'status = "active" AND duration > 60'
        )

    def test_invalid_attribute_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid"):
            SearchExperimentsUtils.validate_filter_string('nonexistent = "x"')

    def test_invalid_entity_type_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid"):
            SearchExperimentsUtils.validate_filter_string('dataset.name = "x"')

    def test_valid_or(self) -> None:
        SearchExperimentsUtils.validate_filter_string(
            'name LIKE "%bert%" OR tags LIKE "%prod%"'
        )

    def test_invalid_syntax_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid"):
            SearchExperimentsUtils.validate_filter_string("name LIKE %bert%")


class TestListGroupExperimentsPaginationFilterString:
    @pytest.fixture
    def backend(self, tmp_path: Path) -> SQLiteBackend:
        return SQLiteBackend(str(tmp_path / "experiments"))

    @pytest.fixture
    def group_ids(self, backend: SQLiteBackend) -> dict[str, str]:
        backend.initialize_experiment(
            "exp-1", group="g1", name="bert_base", tags=["production"]
        )
        backend.initialize_experiment(
            "exp-2", group="g1", name="bert_large", tags=["staging"]
        )
        backend.initialize_experiment(
            "exp-3", group="g1", name="gpt2", tags=["production"]
        )

        backend.log_static("exp-1", "lr", 0.001)
        backend.log_dynamic("exp-1", "accuracy", 0.95)
        backend.end_experiment("exp-1")

        backend.log_static("exp-2", "lr", 0.01)
        backend.log_dynamic("exp-2", "accuracy", 0.88)
        backend.end_experiment("exp-2")

        backend.log_static("exp-3", "lr", 0.001)
        backend.log_dynamic("exp-3", "accuracy", 0.92)
        backend.end_experiment("exp-3")

        conn = backend._get_meta_connection()
        row = conn.execute(
            "SELECT id FROM experiment_groups WHERE name = 'g1'"
        ).fetchone()
        return {"g1": row[0]}

    def test_no_filter_returns_all(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(group_id=group_ids["g1"])
        assert len(result.items) == 3

    def test_filter_by_name_like(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='name LIKE "%bert%"',
        )
        assert len(result.items) == 2
        assert all("bert" in e.name for e in result.items)

    def test_filter_by_tags_like(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='tags LIKE "%production%"',
        )
        assert len(result.items) == 2

    def test_filter_by_tags_contains(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='tags CONTAINS "staging"',
        )
        assert len(result.items) == 1
        assert result.items[0].name == "bert_large"

    def test_filter_by_metric(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search="metric.accuracy > 0.9",
        )
        assert len(result.items) == 2

    def test_filter_by_param(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search="param.lr = 0.001",
        )
        assert len(result.items) == 2

    def test_combined_filter(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='name LIKE "%bert%" AND metric.accuracy > 0.9',
        )
        assert len(result.items) == 1
        assert result.items[0].name == "bert_base"

    def test_filter_or(self, backend: SQLiteBackend, group_ids: dict[str, str]) -> None:
        # bert_base (name match), bert_large (name match), gpt2 (tags=production)
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='name LIKE "%bert%" OR tags LIKE "%production%"',
        )
        assert len(result.items) == 3

    def test_invalid_filter_string_raises(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        with pytest.raises(LumlFilterError, match="Invalid"):
            backend.list_group_experiments_pagination(
                group_id=group_ids["g1"],
                search='nonexistent_col = "x"',
            )

    def test_filter_parens_or_and_status(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        # (bert names OR production tags) AND status = "completed"
        # bert_base: name matches; bert_large: name matches; gpt2: tags=["production"] matches
        result = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='(name LIKE "%bert%" OR tags LIKE "%production%") AND status = "completed"',
        )
        assert len(result.items) == 3

    def test_pagination_with_filter(
        self, backend: SQLiteBackend, group_ids: dict[str, str]
    ) -> None:
        page1 = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='tags LIKE "%production%"',
            limit=1,
            sort_by="name",
            order="asc",
        )
        assert len(page1.items) == 1
        assert page1.cursor is not None

        page2 = backend.list_group_experiments_pagination(
            group_id=group_ids["g1"],
            search='tags LIKE "%production%"',
            limit=1,
            sort_by="name",
            order="asc",
            cursor_str=page1.cursor,
        )
        assert len(page2.items) == 1
        assert page1.items[0].name != page2.items[0].name
