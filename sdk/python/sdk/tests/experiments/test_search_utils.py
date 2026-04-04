# flake8: noqa: E501

import pytest

from luml.experiments.backends._exceptions import LumlFilterError
from luml.experiments.backends._search_utils import (
    SearchEvalsUtils,
    SearchExperimentsUtils,
    SearchTracesUtils,
)


class TestParseSearchFilter:
    def test_empty_returns_empty(self) -> None:
        assert SearchExperimentsUtils.parse_search_filter(None) == []
        assert SearchExperimentsUtils.parse_search_filter("") == []

    def test_attribute_string_eq(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('name = "bert"')
        assert result == [
            {"type": "attribute", "key": "name", "comparator": "=", "value": "bert"}
        ]

    def test_attribute_string_like(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('name LIKE "%bert%"')
        assert result == [
            {
                "type": "attribute",
                "key": "name",
                "comparator": "LIKE",
                "value": "%bert%",
            }
        ]

    def test_attribute_numeric_duration(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("duration > 60")
        assert result == [
            {"type": "attribute", "key": "duration", "comparator": ">", "value": 60.0}
        ]

    def test_attribute_created_at_string(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('created_at > "2024-01-01"')
        assert result == [
            {
                "type": "attribute",
                "key": "created_at",
                "comparator": ">",
                "value": "2024-01-01",
            }
        ]

    def test_tags_like(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('tags LIKE "%prod%"')
        assert result == [
            {"type": "tag", "key": "tags", "comparator": "LIKE", "value": "%prod%"}
        ]

    def test_tags_contains_converts_to_like(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('tags CONTAINS "prod"')
        assert result == [
            {"type": "tag", "key": "tags", "comparator": "LIKE", "value": "%prod%"}
        ]

    def test_tags_contains_case_insensitive(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('tags contains "prod"')
        assert result[0]["comparator"] == "LIKE"
        assert result[0]["value"] == "%prod%"

    def test_param_dot_notation(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("param.lr = 0.001")
        assert result == [
            {"type": "param", "key": "lr", "comparator": "=", "value": 0.001}
        ]

    def test_params_alias(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("params.lr = 0.001")
        assert result[0]["type"] == "param"
        assert result[0]["key"] == "lr"

    def test_static_params_alias(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("static_params.lr = 0.001")
        assert result[0]["type"] == "param"

    def test_metric_dot_notation(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("metric.accuracy > 0.9")
        assert result == [
            {"type": "metric", "key": "accuracy", "comparator": ">", "value": 0.9}
        ]

    def test_metrics_alias(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("metrics.loss < 0.5")
        assert result[0]["type"] == "metric"

    def test_dynamic_params_alias(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("dynamic_params.f1 >= 0.8")
        assert result[0]["type"] == "metric"
        assert result[0]["key"] == "f1"

    def test_attribute_prefix(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('attribute.name = "test"')
        assert result[0]["type"] == "attribute"
        assert result[0]["key"] == "name"

    def test_multiple_and_clauses(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            'status = "active" AND duration > 60'
        )
        assert len(result) == 3
        assert result[0] == {
            "type": "attribute",
            "key": "status",
            "comparator": "=",
            "value": "active",
        }
        assert result[1] == {"operator": "AND"}
        assert result[2] == {
            "type": "attribute",
            "key": "duration",
            "comparator": ">",
            "value": 60.0,
        }

    def test_or_clause(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            'name LIKE "%bert%" OR tags LIKE "%prod%"'
        )
        assert len(result) == 3
        assert result[0] == {
            "type": "attribute",
            "key": "name",
            "comparator": "LIKE",
            "value": "%bert%",
        }
        assert result[1] == {"operator": "OR"}
        assert result[2] == {
            "type": "tag",
            "key": "tags",
            "comparator": "LIKE",
            "value": "%prod%",
        }

    def test_and_or_mixed(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            'name LIKE "%bert%" AND status = "active" OR tags LIKE "%prod%"'
        )
        assert len(result) == 5
        operators = [r["operator"] for r in result if "operator" in r]
        assert operators == ["AND", "OR"]

    def test_parenthesized_or(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            '(name LIKE "%bert%" OR tags LIKE "%prod%")'
        )
        assert len(result) == 1
        assert "group" in result[0]
        inner = result[0]["group"]
        assert len(inner) == 3
        assert inner[0] == {
            "type": "attribute",
            "key": "name",
            "comparator": "LIKE",
            "value": "%bert%",
        }
        assert inner[1] == {"operator": "OR"}
        assert inner[2] == {
            "type": "tag",
            "key": "tags",
            "comparator": "LIKE",
            "value": "%prod%",
        }

    def test_parenthesized_or_and_and(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            '(name LIKE "%bert%" OR tags LIKE "%prod%") AND status = "active"'
        )
        assert len(result) == 3
        assert "group" in result[0]
        inner = result[0]["group"]
        operators = [r["operator"] for r in inner if "operator" in r]
        assert "OR" in operators
        assert result[1] == {"operator": "AND"}
        assert result[2]["key"] == "status"

    def test_invalid_attribute_key_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid attribute key"):
            SearchExperimentsUtils.parse_search_filter('nonexistent_col = "x"')

    def test_invalid_entity_type_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid entity type"):
            SearchExperimentsUtils.parse_search_filter('dataset.name = "x"')


class TestToSqlWhereClause:
    def test_none_filter(self) -> None:
        w, o, p = SearchExperimentsUtils.to_sql(None)
        assert w == ""
        assert o == ""
        assert p == []

    def test_name_like(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('name LIKE "%bert%"')
        assert w == "name LIKE ?"
        assert p == ["%bert%"]

    def test_status_eq(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('status = "active"')
        assert w == "status = ?"
        assert p == ["active"]

    def test_status_neq(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('status != "deleted"')
        assert w == "status != ?"
        assert p == ["deleted"]

    def test_duration_gt(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql("duration > 60")
        assert w == "duration > ?"
        assert p == [60.0]

    def test_duration_lte(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql("duration <= 3600")
        assert w == "duration <= ?"
        assert p == [3600.0]

    def test_created_at_string(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('created_at > "2024-01-01"')
        assert w == "created_at > ?"
        assert p == ["2024-01-01"]

    def test_tags_like(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('tags LIKE "%prod%"')
        assert w == "tags LIKE ?"
        assert p == ["%prod%"]

    def test_tags_contains(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('tags CONTAINS "prod"')
        assert w == "tags LIKE ?"
        assert p == ["%prod%"]

    def test_tags_ilike(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('tags ILIKE "%Prod%"')
        assert w == "UPPER(tags) LIKE UPPER(?)"
        assert p == ["%Prod%"]

    def test_param_numeric(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql("param.lr = 0.001")
        assert w == "json_extract(static_params, '$.lr') = ?"
        assert p == [0.001]

    def test_param_string(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('param.optimizer = "adam"')
        assert w == "json_extract(static_params, '$.optimizer') = ?"
        assert p == ["adam"]

    def test_param_like(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('param.model_name LIKE "%bert%"')
        assert w == "json_extract(static_params, '$.model_name') LIKE ?"
        assert p == ["%bert%"]

    def test_param_ilike(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('param.model ILIKE "%BERT%"')
        assert "UPPER" in w
        assert p == ["%BERT%"]

    def test_metric_gt(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql("metric.accuracy > 0.9")
        assert w == "json_extract(dynamic_params, '$.accuracy') > ?"
        assert p == [0.9]

    def test_metric_lt(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql("metric.loss < 0.5")
        assert w == "json_extract(dynamic_params, '$.loss') < ?"
        assert p == [0.5]

    def test_name_ilike(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('name ILIKE "%BERT%"')
        assert w == "UPPER(name) LIKE UPPER(?)"
        assert p == ["%BERT%"]

    def test_in_clause(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('status IN ("active", "completed")')
        assert w == "status IN (?,?)"
        assert p == ["active", "completed"]

    def test_not_in_clause(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('status NOT IN ("deleted",)')
        assert "NOT IN" in w
        assert "deleted" in p

    def test_combined_and(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql('status = "active" AND duration > 60')
        assert w == "status = ? AND duration > ?"
        assert p == ["active", 60.0]

    def test_or_clause(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql(
            'name LIKE "%bert%" OR tags LIKE "%prod%"'
        )
        assert w == "name LIKE ? OR tags LIKE ?"
        assert p == ["%bert%", "%prod%"]

    def test_and_or_mixed(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql(
            'status = "active" AND name LIKE "%bert%" OR tags LIKE "%prod%"'
        )
        assert w == "status = ? AND name LIKE ? OR tags LIKE ?"
        assert p == ["active", "%bert%", "%prod%"]

    def test_parens_or_and_and(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql(
            '(name LIKE "%bert%" OR tags LIKE "%prod%") AND status = "active"'
        )
        assert w == "(name LIKE ? OR tags LIKE ?) AND status = ?"
        assert p == ["%bert%", "%prod%", "active"]

    def test_parens_and_or_parens(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql(
            'status = "active" AND (metric.accuracy > 0.9 OR param.lr = 0.001)'
        )
        assert (
            w
            == "status = ? AND (json_extract(dynamic_params, '$.accuracy') > ? OR json_extract(static_params, '$.lr') = ?)"
        )
        assert p == ["active", 0.9, 0.001]

    def test_three_clauses(self) -> None:
        w, _, p = SearchExperimentsUtils.to_sql(
            'status = "active" AND metric.accuracy > 0.9 AND param.lr = 0.001'
        )
        assert w.count("AND") == 2
        assert len(p) == 3

    def test_static_params_alias_sql(self) -> None:
        w1, _, _ = SearchExperimentsUtils.to_sql("static_params.lr = 0.001")
        w2, _, _ = SearchExperimentsUtils.to_sql("param.lr = 0.001")
        assert w1 == w2

    def test_dynamic_params_alias_sql(self) -> None:
        w1, _, _ = SearchExperimentsUtils.to_sql("dynamic_params.acc > 0.9")
        w2, _, _ = SearchExperimentsUtils.to_sql("metric.acc > 0.9")
        assert w1 == w2


class TestToSqlOrderBy:
    def test_no_order_by(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, None)
        assert o == ""

    def test_single_desc(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["created_at DESC"])
        assert o == "ORDER BY created_at DESC"

    def test_single_asc(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["name ASC"])
        assert o == "ORDER BY name ASC"

    def test_default_asc(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["name"])
        assert o == "ORDER BY name ASC"

    def test_multiple_order_by(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["created_at DESC", "name ASC"])
        assert o == "ORDER BY created_at DESC, name ASC"

    def test_param_order_by(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["param.lr ASC"])
        assert o == "ORDER BY json_extract(static_params, '$.lr') ASC"

    def test_metric_order_by(self) -> None:
        _, o, _ = SearchExperimentsUtils.to_sql(None, ["metric.accuracy DESC"])
        assert o == "ORDER BY json_extract(dynamic_params, '$.accuracy') DESC"

    def test_filter_and_order_by(self) -> None:
        w, o, p = SearchExperimentsUtils.to_sql(
            'name LIKE "%bert%"', ["created_at DESC"]
        )
        assert w == "name LIKE ?"
        assert o == "ORDER BY created_at DESC"
        assert p == ["%bert%"]

    def test_invalid_order_by_key_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid attribute key"):
            SearchExperimentsUtils.to_sql(None, ["nonexistent_col DESC"])

    def test_invalid_order_by_format_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid order_by clause"):
            SearchExperimentsUtils.to_sql(None, ["name ASC DESC"])


class TestParseOrderBy:
    def test_attribute_asc(self) -> None:
        t, k, asc = SearchExperimentsUtils.parse_order_by("name ASC")
        assert t == "attribute"
        assert k == "name"
        assert asc is True

    def test_attribute_desc(self) -> None:
        t, k, asc = SearchExperimentsUtils.parse_order_by("created_at DESC")
        assert t == "attribute"
        assert k == "created_at"
        assert asc is False

    def test_default_asc(self) -> None:
        t, k, asc = SearchExperimentsUtils.parse_order_by("name")
        assert asc is True

    def test_param_order_by(self) -> None:
        t, k, asc = SearchExperimentsUtils.parse_order_by("param.lr ASC")
        assert t == "param"
        assert k == "lr"
        assert asc is True

    def test_metric_order_by(self) -> None:
        t, k, asc = SearchExperimentsUtils.parse_order_by("metric.accuracy DESC")
        assert t == "metric"
        assert k == "accuracy"
        assert asc is False


class TestSearchEvalsUtilsToSql:
    def test_none_returns_empty(self) -> None:
        w, p = SearchEvalsUtils.to_sql(None)
        assert w == ""
        assert p == []

    def test_id_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id = "abc123"')
        assert w == "id = ?"
        assert p == ["abc123"]

    def test_dataset_id_like(self) -> None:
        w, p = SearchEvalsUtils.to_sql('dataset_id LIKE "%ds%"')
        assert w == "dataset_id LIKE ?"
        assert p == ["%ds%"]

    def test_id_contains(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id CONTAINS "abc"')
        assert w == "id LIKE ?"
        assert p == ["%abc%"]

    def test_created_at_gt(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at > "2024-01-01"')
        assert w == "created_at > ?"
        assert p == ["2024-01-01"]

    def test_updated_at_lte(self) -> None:
        w, p = SearchEvalsUtils.to_sql('updated_at <= "2024-12-31"')
        assert w == "updated_at <= ?"
        assert p == ["2024-12-31"]

    def test_outputs_string_like(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.prediction LIKE "%bert%"')
        assert w == "json_extract(outputs, '$.prediction') LIKE ?"
        assert p == ["%bert%"]

    def test_scores_numeric_gt(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.accuracy > 0.9")
        assert w == "json_extract(scores, '$.accuracy') > ?"
        assert p == [0.9]

    def test_inputs_contains(self) -> None:
        w, p = SearchEvalsUtils.to_sql('inputs.question CONTAINS "what"')
        assert w == "json_extract(inputs, '$.question') LIKE ?"
        assert p == ["%what%"]

    def test_metadata_numeric_lt(self) -> None:
        w, p = SearchEvalsUtils.to_sql("metadata.latency_ms < 100")
        assert w == "json_extract(metadata, '$.latency_ms') < ?"
        assert p == [100.0]

    def test_refs_string_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('refs.answer = "yes"')
        assert w == "json_extract(refs, '$.answer') = ?"
        assert p == ["yes"]

    def test_outputs_ilike(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.label ILIKE "%Yes%"')
        assert w == "UPPER(json_extract(outputs, '$.label')) LIKE UPPER(?)"
        assert p == ["%Yes%"]

    def test_invalid_bare_attribute_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('nonexistent_col = "x"')

    def test_invalid_column_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('invalid_col.key = "val"')

    def test_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql("scores.accuracy => 0.5")


class TestSearchEvalsUtilsValidate:
    def test_none_is_valid(self) -> None:
        SearchEvalsUtils.validate_filter_string(None)  # should not raise

    def test_valid_filter_passes(self) -> None:
        SearchEvalsUtils.validate_filter_string('outputs.prediction LIKE "%bert%"')

    def test_valid_date_filter_passes(self) -> None:
        SearchEvalsUtils.validate_filter_string('created_at > "2024-01-01"')

    def test_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.validate_filter_string("scores.accuracy => 0.5")

    def test_invalid_column_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.validate_filter_string('bad_column.key = "x"')


class TestSearchTracesUtilsToSql:
    def test_none_returns_empty(self) -> None:
        w, p = SearchTracesUtils.to_sql(None)
        assert w == ""
        assert p == []

    def test_attribute_string_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.http.method = "GET"')
        assert "trace_id IN" in w
        assert "SELECT DISTINCT trace_id FROM spans" in w
        assert "json_extract(attributes, '$.\"http.method\"') = ?" in w
        assert p == ["GET"]

    def test_attribute_numeric_gte(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.http.status_code >= 400")
        assert "json_extract(attributes, '$.\"http.status_code\"') >= ?" in w
        assert p == [400.0]

    def test_attribute_contains(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.db.statement CONTAINS "SELECT"')
        assert "json_extract(attributes, '$.\"db.statement\"') LIKE ?" in w
        assert p == ["%SELECT%"]

    def test_attribute_ilike(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.service.name ILIKE "%api%"')
        assert (
            "UPPER(json_extract(attributes, '$.\"service.name\"')) LIKE UPPER(?)" in w
        )
        assert p == ["%api%"]

    def test_no_attributes_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql('http.method = "GET"')

    def test_bare_key_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql('method = "GET"')

    def test_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql("attributes.http.status_code => 400")


class TestSearchTracesUtilsValidate:
    def test_none_is_valid(self) -> None:
        SearchTracesUtils.validate_filter_string(None)  # should not raise

    def test_valid_filter_passes(self) -> None:
        SearchTracesUtils.validate_filter_string('attributes.http.method = "GET"')

    def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.validate_filter_string('http.method = "GET"')

    def test_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.validate_filter_string("attributes.code >= === 400")


# ---------------------------------------------------------------------------
# Evals — bare string attributes: id, dataset_id
# Allowed: = != LIKE ILIKE IN NOT IN CONTAINS
# Forbidden: > >= < <=
# ---------------------------------------------------------------------------
class TestSearchEvalsStringAttributes:
    def test_id_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id = "abc123"')
        assert w == "id = ?"
        assert p == ["abc123"]

    def test_id_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id != "abc123"')
        assert w == "id != ?"
        assert p == ["abc123"]

    def test_id_like(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id LIKE "%abc%"')
        assert w == "id LIKE ?"
        assert p == ["%abc%"]

    def test_id_ilike(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id ILIKE "%ABC%"')
        assert w == "UPPER(id) LIKE UPPER(?)"
        assert p == ["%ABC%"]

    def test_id_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id IN ("abc", "def")')
        assert w == "id IN (?,?)"
        assert p == ["abc", "def"]

    def test_id_not_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id NOT IN ("abc", "def")')
        assert "id NOT IN" in w
        assert p == ["abc", "def"]

    def test_id_contains(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id CONTAINS "abc"')
        assert w == "id LIKE ?"
        assert p == ["%abc%"]

    def test_dataset_id_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('dataset_id = "ds-001"')
        assert w == "dataset_id = ?"
        assert p == ["ds-001"]

    def test_id_gt_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('id > "abc"')

    def test_id_gte_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('id >= "abc"')

    def test_id_lt_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('id < "abc"')

    def test_id_lte_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('id <= "abc"')


# ---------------------------------------------------------------------------
# Evals — date attributes: created_at, updated_at
# Allowed: = != > >= < <=
# Forbidden: LIKE ILIKE IN NOT IN CONTAINS
# ---------------------------------------------------------------------------
class TestSearchEvalsDateAttributes:
    def test_created_at_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at = "2024-01-01"')
        assert w == "created_at = ?"
        assert p == ["2024-01-01"]

    def test_created_at_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at != "2024-01-01"')
        assert w == "created_at != ?"
        assert p == ["2024-01-01"]

    def test_created_at_gt(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at > "2024-01-01"')
        assert w == "created_at > ?"
        assert p == ["2024-01-01"]

    def test_created_at_gte(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at >= "2024-01-01"')
        assert w == "created_at >= ?"
        assert p == ["2024-01-01"]

    def test_created_at_lt(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at < "2024-12-31"')
        assert w == "created_at < ?"
        assert p == ["2024-12-31"]

    def test_created_at_lte(self) -> None:
        w, p = SearchEvalsUtils.to_sql('created_at <= "2024-12-31"')
        assert w == "created_at <= ?"
        assert p == ["2024-12-31"]

    def test_updated_at_gt(self) -> None:
        w, p = SearchEvalsUtils.to_sql('updated_at > "2024-06-01"')
        assert w == "updated_at > ?"
        assert p == ["2024-06-01"]

    def test_created_at_like_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('created_at LIKE "%2024%"')

    def test_created_at_ilike_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('created_at ILIKE "%2024%"')

    def test_created_at_in_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('created_at IN ("2024-01-01")')

    def test_created_at_not_in_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('created_at NOT IN ("2024-01-01")')

    def test_created_at_contains_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchEvalsUtils.to_sql('created_at CONTAINS "2024"')


# ---------------------------------------------------------------------------
# Evals — JSON fields: inputs.*, outputs.*, refs.*, scores.*, metadata.*
# All operators allowed; type auto-detected from value
# ---------------------------------------------------------------------------
class TestSearchEvalsJsonFields:
    # --- string ---
    def test_outputs_string_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.label = "positive"')
        assert w == "json_extract(outputs, '$.label') = ?"
        assert p == ["positive"]

    def test_outputs_string_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.label != "negative"')
        assert w == "json_extract(outputs, '$.label') != ?"
        assert p == ["negative"]

    def test_outputs_string_like(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.text LIKE "%hello%"')
        assert w == "json_extract(outputs, '$.text') LIKE ?"
        assert p == ["%hello%"]

    def test_outputs_string_ilike(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.text ILIKE "%HELLO%"')
        assert w == "UPPER(json_extract(outputs, '$.text')) LIKE UPPER(?)"
        assert p == ["%HELLO%"]

    def test_outputs_string_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.label IN ("pos", "neg")')
        assert w == "json_extract(outputs, '$.label') IN (?,?)"
        assert p == ["pos", "neg"]

    def test_outputs_string_not_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.label NOT IN ("pos", "neg")')
        assert "json_extract(outputs, '$.label') NOT IN" in w
        assert p == ["pos", "neg"]

    def test_outputs_string_contains(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.text CONTAINS "hello"')
        assert w == "json_extract(outputs, '$.text') LIKE ?"
        assert p == ["%hello%"]

    # --- number ---
    def test_scores_number_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.accuracy = 1.0")
        assert w == "json_extract(scores, '$.accuracy') = ?"
        assert p == [1.0]

    def test_scores_number_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.accuracy != 0.0")
        assert w == "json_extract(scores, '$.accuracy') != ?"
        assert p == [0.0]

    def test_scores_number_gt(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.accuracy > 0.9")
        assert w == "json_extract(scores, '$.accuracy') > ?"
        assert p == [0.9]

    def test_scores_number_gte(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.f1 >= 0.8")
        assert w == "json_extract(scores, '$.f1') >= ?"
        assert p == [0.8]

    def test_scores_number_lt(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.loss < 0.5")
        assert w == "json_extract(scores, '$.loss') < ?"
        assert p == [0.5]

    def test_metadata_number_lte(self) -> None:
        w, p = SearchEvalsUtils.to_sql("metadata.latency_ms <= 200")
        assert w == "json_extract(metadata, '$.latency_ms') <= ?"
        assert p == [200.0]

    # --- boolean ---
    def test_metadata_bool_true_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql("metadata.normalize = true")
        assert w == "json_extract(metadata, '$.normalize') = ?"
        assert p == [1.0]

    def test_metadata_bool_false_eq(self) -> None:
        w, p = SearchEvalsUtils.to_sql("metadata.normalize = false")
        assert w == "json_extract(metadata, '$.normalize') = ?"
        assert p == [0.0]

    def test_metadata_bool_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql("metadata.active != true")
        assert w == "json_extract(metadata, '$.active') != ?"
        assert p == [1.0]

    def test_bool_python_style_True(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.passed = True")
        assert p == [1.0]

    def test_bool_python_style_False(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.passed = False")
        assert p == [0.0]

    def test_bool_uppercase_TRUE(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.passed = TRUE")
        assert p == [1.0]

    # --- all json columns accessible ---
    def test_inputs_field(self) -> None:
        w, _ = SearchEvalsUtils.to_sql('inputs.question LIKE "%what%"')
        assert "json_extract(inputs, '$.question')" in w

    def test_refs_field(self) -> None:
        w, _ = SearchEvalsUtils.to_sql('refs.answer = "yes"')
        assert "json_extract(refs, '$.answer')" in w

    def test_metadata_field(self) -> None:
        w, _ = SearchEvalsUtils.to_sql("metadata.latency_ms > 100")
        assert "json_extract(metadata, '$.latency_ms')" in w


# ---------------------------------------------------------------------------
# Traces — attributes.*
# All operators allowed; type auto-detected from value
# ---------------------------------------------------------------------------
class TestSearchTracesAllOperators:
    # --- string ---
    def test_attr_string_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.http.method = "GET"')
        assert "json_extract(attributes, '$.\"http.method\"') = ?" in w
        assert p == ["GET"]

    def test_attr_string_neq(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.http.method != "POST"')
        assert "json_extract(attributes, '$.\"http.method\"') != ?" in w
        assert p == ["POST"]

    def test_attr_string_like(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.service.name LIKE "%api%"')
        assert "json_extract(attributes, '$.\"service.name\"') LIKE ?" in w
        assert p == ["%api%"]

    def test_attr_string_ilike(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.service.name ILIKE "%API%"')
        assert (
            "UPPER(json_extract(attributes, '$.\"service.name\"')) LIKE UPPER(?)" in w
        )
        assert p == ["%API%"]

    def test_attr_string_in(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.http.method IN ("GET", "POST")')
        assert "json_extract(attributes, '$.\"http.method\"') IN (?,?)" in w
        assert p == ["GET", "POST"]

    def test_attr_string_not_in(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            'attributes.http.method NOT IN ("DELETE", "PUT")'
        )
        assert "NOT IN" in w
        assert p == ["DELETE", "PUT"]

    def test_attr_string_contains(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.db.statement CONTAINS "SELECT"')
        assert "json_extract(attributes, '$.\"db.statement\"') LIKE ?" in w
        assert p == ["%SELECT%"]

    # --- number ---
    def test_attr_number_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.http.status_code = 200")
        assert "json_extract(attributes, '$.\"http.status_code\"') = ?" in w
        assert p == [200.0]

    def test_attr_number_neq(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.http.status_code != 404")
        assert "json_extract(attributes, '$.\"http.status_code\"') != ?" in w
        assert p == [404.0]

    def test_attr_number_gt(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.http.status_code > 400")
        assert "json_extract(attributes, '$.\"http.status_code\"') > ?" in w
        assert p == [400.0]

    def test_attr_number_gte(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.http.status_code >= 500")
        assert "json_extract(attributes, '$.\"http.status_code\"') >= ?" in w
        assert p == [500.0]

    def test_attr_number_lt(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.duration_ms < 1000")
        assert "json_extract(attributes, '$.\"duration_ms\"') < ?" in w
        assert p == [1000.0]

    def test_attr_number_lte(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.retry_count <= 3")
        assert "json_extract(attributes, '$.\"retry_count\"') <= ?" in w
        assert p == [3.0]

    # --- boolean ---
    def test_attr_bool_true_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.error = true")
        assert "json_extract(attributes, '$.\"error\"') = ?" in w
        assert p == [1.0]

    def test_attr_bool_false_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.error = false")
        assert "json_extract(attributes, '$.\"error\"') = ?" in w
        assert p == [0.0]

    def test_attr_bool_neq(self) -> None:
        w, p = SearchTracesUtils.to_sql("attributes.is_root != true")
        assert "json_extract(attributes, '$.\"is_root\"') != ?" in w
        assert p == [1.0]

    def test_attr_bool_python_style_True(self) -> None:
        _, p = SearchTracesUtils.to_sql("attributes.error = True")
        assert p == [1.0]

    def test_attr_bool_python_style_False(self) -> None:
        _, p = SearchTracesUtils.to_sql("attributes.error = False")
        assert p == [0.0]

    def test_attr_bool_uppercase_TRUE(self) -> None:
        _, p = SearchTracesUtils.to_sql("attributes.error = TRUE")
        assert p == [1.0]

    # --- error cases ---
    def test_missing_attributes_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql('http.method = "GET"')

    def test_bare_key_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql('method = "GET"')

    def test_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.to_sql("attributes.status_code => 400")


class TestSearchEvalsAnnotationUnderscoreSyntax:
    def test_annotations_feedback_eq_string(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_feedback.quality = "true"')
        assert w == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'feedback' AND value = ?)"
        assert p == ["quality", "true"]

    def test_annotations_expectations_eq_string(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_expectations.expected_answer = "bird"')
        assert w == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'expectation' AND value = ?)"
        assert p == ["expected_answer", "bird"]

    def test_annotations_expectation_singular_eq_string(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_expectation.expected_answer = "bird"')
        assert w == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'expectation' AND value = ?)"
        assert p == ["expected_answer", "bird"]

    def test_annotations_feedback_name_with_underscores(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_feedback.my_score = "good"')
        assert "annotation_kind = 'feedback'" in w
        assert p == ["my_score", "good"]

    def test_annotations_expectations_name_with_underscores(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_expectations.expected_output = "yes"')
        assert "annotation_kind = 'expectation'" in w
        assert p == ["expected_output", "yes"]

    def test_annotations_feedback_neq(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_feedback.quality != "bad"')
        assert "annotation_kind = 'feedback'" in w
        assert "value != ?" in w
        assert p == ["quality", "bad"]

    def test_annotations_expectation_and_feedback_combined(self) -> None:
        w, p = SearchEvalsUtils.to_sql(
            'annotations_feedback.quality = "true" AND annotations_expectation.label = "cat"'
        )
        assert "annotation_kind = 'feedback'" in w
        assert "annotation_kind = 'expectation'" in w
        assert "quality" in p
        assert "true" in p
        assert "label" in p
        assert "cat" in p


class TestSearchTracesAnnotationUnderscoreSyntax:
    def test_annotations_feedback_eq_string(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_feedback.quality = "true"')
        assert w == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'feedback' AND value = ?)"
        assert p == ["quality", "true"]

    def test_annotations_expectations_eq_string(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_expectations.expected_answer = "bird"')
        assert w == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'expectation' AND value = ?)"
        assert p == ["expected_answer", "bird"]

    def test_annotations_expectation_singular_eq_string(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_expectation.expected_answer = "bird"')
        assert w == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'expectation' AND value = ?)"
        assert p == ["expected_answer", "bird"]

    def test_annotations_feedback_name_with_underscores(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_feedback.my_score = "ok"')
        assert "annotation_kind = 'feedback'" in w
        assert p == ["my_score", "ok"]

    def test_annotations_expectations_name_with_underscores(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_expectations.expected_output = "yes"')
        assert "annotation_kind = 'expectation'" in w
        assert p == ["expected_output", "yes"]

    def test_annotations_feedback_neq(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_feedback.quality != "bad"')
        assert "annotation_kind = 'feedback'" in w
        assert "value != ?" in w
        assert p == ["quality", "bad"]

    def test_annotations_expectation_and_feedback_combined(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            'annotations_feedback.rating = "high" AND annotations_expectation.label = "dog"'
        )
        assert "annotation_kind = 'feedback'" in w
        assert "annotation_kind = 'expectation'" in w
        assert "rating" in p
        assert "high" in p
        assert "label" in p
        assert "dog" in p
