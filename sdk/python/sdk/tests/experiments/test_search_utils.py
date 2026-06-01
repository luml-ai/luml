# flake8: noqa: E501

from typing import Any
from unittest.mock import patch

import pytest
from sqlparse.sql import Token as SqlToken
from sqlparse.tokens import Token as TokenType

from luml.experiments.backends._exceptions import LumlFilterError
from luml.experiments.backends._search_utils import (
    SearchEvalsUtils,
    SearchExperimentsUtils,
    SearchTracesUtils,
    SearchUtils,
    _ilike,
    _like,
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

    def test_bool_python_style_true(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.passed = True")
        assert p == [1.0]

    def test_bool_python_style_false(self) -> None:
        w, p = SearchEvalsUtils.to_sql("scores.passed = False")
        assert p == [0.0]

    def test_bool_uppercase_true(self) -> None:
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

    def test_attr_bool_python_style_true(self) -> None:
        _, p = SearchTracesUtils.to_sql("attributes.error = True")
        assert p == [1.0]

    def test_attr_bool_python_style_false(self) -> None:
        _, p = SearchTracesUtils.to_sql("attributes.error = False")
        assert p == [0.0]

    def test_attr_bool_uppercase_true(self) -> None:
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
        assert (
            w
            == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'feedback' AND value = ?)"
        )
        assert p == ["quality", "true"]

    def test_annotations_expectations_eq_string(self) -> None:
        w, p = SearchEvalsUtils.to_sql(
            'annotations_expectations.expected_answer = "bird"'
        )
        assert (
            w
            == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'expectation' AND value = ?)"
        )
        assert p == ["expected_answer", "bird"]

    def test_annotations_expectation_singular_eq_string(self) -> None:
        w, p = SearchEvalsUtils.to_sql(
            'annotations_expectation.expected_answer = "bird"'
        )
        assert (
            w
            == "EXISTS (SELECT 1 FROM eval_annotations WHERE eval_id = evals.id AND name = ? AND annotation_kind = 'expectation' AND value = ?)"
        )
        assert p == ["expected_answer", "bird"]

    def test_annotations_feedback_name_with_underscores(self) -> None:
        w, p = SearchEvalsUtils.to_sql('annotations_feedback.my_score = "good"')
        assert "annotation_kind = 'feedback'" in w
        assert p == ["my_score", "good"]

    def test_annotations_expectations_name_with_underscores(self) -> None:
        w, p = SearchEvalsUtils.to_sql(
            'annotations_expectations.expected_output = "yes"'
        )
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
        assert (
            w
            == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'feedback' AND value = ?)"
        )
        assert p == ["quality", "true"]

    def test_annotations_expectations_eq_string(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            'annotations_expectations.expected_answer = "bird"'
        )
        assert (
            w
            == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'expectation' AND value = ?)"
        )
        assert p == ["expected_answer", "bird"]

    def test_annotations_expectation_singular_eq_string(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            'annotations_expectation.expected_answer = "bird"'
        )
        assert (
            w
            == "trace_id IN (SELECT DISTINCT trace_id FROM span_annotations WHERE name = ? AND annotation_kind = 'expectation' AND value = ?)"
        )
        assert p == ["expected_answer", "bird"]

    def test_annotations_feedback_name_with_underscores(self) -> None:
        w, p = SearchTracesUtils.to_sql('annotations_feedback.my_score = "ok"')
        assert "annotation_kind = 'feedback'" in w
        assert p == ["my_score", "ok"]

    def test_annotations_expectations_name_with_underscores(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            'annotations_expectations.expected_output = "yes"'
        )
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


class TestSearchUtilsBase:
    """Cover base SearchUtils helpers and shared error paths."""

    def test_like_helper_matches_pattern(self) -> None:
        assert _like("hello world", "%world%") is True
        assert _like("hello", "hello") is True
        assert _like("HELLO", "hello") is False

    def test_ilike_helper_case_insensitive(self) -> None:
        assert _ilike("HELLO", "hello") is True
        assert _ilike("Foo Bar", "%foo%") is True

    def test_like_prefix_anchor(self) -> None:
        assert _like("abc", "ab%") is True
        assert _like("xabc", "ab%") is False

    def test_like_suffix_anchor(self) -> None:
        assert _like("abc", "%bc") is True
        assert _like("abcx", "%bc") is False

    def test_get_comparison_func_all_operators(self) -> None:
        assert SearchUtils.get_comparison_func(">")(2, 1) is True
        assert SearchUtils.get_comparison_func(">=")(1, 1) is True
        assert SearchUtils.get_comparison_func("=")(1, 1) is True
        assert SearchUtils.get_comparison_func("!=")(1, 2) is True
        assert SearchUtils.get_comparison_func("<=")(1, 1) is True
        assert SearchUtils.get_comparison_func("<")(1, 2) is True
        assert SearchUtils.get_comparison_func("LIKE")("abc", "%b%") is True
        assert SearchUtils.get_comparison_func("ILIKE")("ABC", "%b%") is True
        assert SearchUtils.get_comparison_func("IN")(1, [1, 2]) is True
        assert SearchUtils.get_comparison_func("NOT IN")(3, [1, 2]) is True

    def test_build_annotation_value_expr_numeric_comparators(self) -> None:
        for op in (">", ">=", "<", "<="):
            sql, params = SearchUtils._build_annotation_value_expr(op, 5)
            assert sql == f"CAST(value AS REAL) {op} ?"
            assert params == [5]

    def test_build_annotation_value_expr_ilike(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("ILIKE", "%foo%")
        assert sql == "UPPER(value) LIKE UPPER(?)"
        assert params == ["%foo%"]

    def test_build_annotation_value_expr_in_and_not_in(self) -> None:
        sql_in, params_in = SearchUtils._build_annotation_value_expr("IN", ["a", "b"])
        assert sql_in == "value IN (?,?)"
        assert params_in == ["a", "b"]

        sql_not, params_not = SearchUtils._build_annotation_value_expr("NOT IN", ["x"])
        assert sql_not == "value NOT IN (?)"
        assert params_not == ["x"]

    def test_build_annotation_value_expr_float_one_eq(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("=", 1.0)
        assert sql == "(value = ? OR value = 'true')"
        assert params == ["1"]

    def test_build_annotation_value_expr_float_one_neq(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("!=", 1.0)
        assert sql == "(value != ? AND value != 'true')"
        assert params == ["1"]

    def test_build_annotation_value_expr_float_zero_eq(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("=", 0.0)
        assert sql == "(value = ? OR value = 'false')"
        assert params == ["0"]

    def test_build_annotation_value_expr_float_zero_neq(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("!=", 0.0)
        assert sql == "(value != ? AND value != 'false')"
        assert params == ["0"]

    def test_build_annotation_value_expr_float_other(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("=", 3.5)
        assert sql == "value = ?"
        assert params == ["3.5"]

    def test_build_annotation_value_expr_string(self) -> None:
        sql, params = SearchUtils._build_annotation_value_expr("=", "hello")
        assert sql == "value = ?"
        assert params == ["hello"]

    def test_validate_date_string_raises_on_invalid(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid date value"):
            SearchUtils._validate_date_string("not-a-date", "created_at")

    def test_strip_quotes_raises_when_expected(self) -> None:
        with pytest.raises(LumlFilterError, match="not quoted"):
            SearchUtils._strip_quotes("bare_value", expect_quoted_value=True)

    def test_strip_quotes_returns_raw_when_optional(self) -> None:
        assert SearchUtils._strip_quotes("bare", expect_quoted_value=False) == "bare"
        assert SearchUtils._strip_quotes("'q'") == "q"
        assert SearchUtils._strip_quotes('"q"') == "q"

    def test_trim_backticks(self) -> None:
        assert SearchUtils._trim_backticks("`param`") == "param"
        assert SearchUtils._trim_backticks("plain") == "plain"

    def test_invalid_clause_in_filter_string(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid clause"):
            SearchExperimentsUtils.parse_search_filter("name")

    def test_parse_list_raises_for_malformed_syntax(self) -> None:
        class _FakeTok:
            value = "(1, 2"

        with pytest.raises(LumlFilterError, match="ill-formed list"):
            SearchUtils._parse_list_from_sql_token(_FakeTok())

    def test_check_valid_identifier_list_rejects_empty(self) -> None:
        with pytest.raises(LumlFilterError, match="empty list"):
            SearchExperimentsUtils._check_valid_identifier_list(())

    def test_check_valid_identifier_list_rejects_non_string(self) -> None:
        with pytest.raises(LumlFilterError, match="different type"):
            SearchExperimentsUtils._check_valid_identifier_list((1, 2))


class TestSearchExperimentsUtilsBranches:
    """Cover SearchExperimentsUtils edge cases and error paths."""

    def test_preprocess_contains_to_like(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('name CONTAINS "bert"')
        assert result == [
            {
                "type": "attribute",
                "key": "name",
                "comparator": "LIKE",
                "value": "%bert%",
            }
        ]

    def test_invalid_entity_type_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid entity type"):
            SearchExperimentsUtils.parse_search_filter('unknown.foo = "x"')

    def test_invalid_key_for_param_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid key"):
            SearchExperimentsUtils.parse_search_filter('param."bad key!" = "x"')

    def test_metric_non_numeric_value_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected numeric value type for metric"
        ):
            SearchExperimentsUtils.parse_search_filter('metric.acc = "string"')

    def test_param_boolean_value(self) -> None:
        # "true" is preprocessed to 1 then converted to float
        result = SearchExperimentsUtils.parse_search_filter("param.enabled = true")
        assert result[0]["value"] == 1.0

    def test_param_invalid_value_type_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected string or numeric value for param"
        ):
            SearchExperimentsUtils.parse_search_filter("param.lr = (1, 2)")

    def test_tag_unquoted_value_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected quoted string value for tag"
        ):
            SearchExperimentsUtils.parse_search_filter("tags = (1, 2)")

    def test_duration_string_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected numeric value for 'duration'"
        ):
            SearchExperimentsUtils.parse_search_filter('duration = "fast"')

    def test_created_at_numeric_accepted(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter("created_at > 1234567")
        assert result[0]["key"] == "created_at"

    def test_created_at_invalid_token_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Expected quoted date string"):
            SearchExperimentsUtils.parse_search_filter("created_at = (1, 2)")

    def test_attribute_in_with_list(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter(
            'status IN ("active", "completed")'
        )
        assert result[0]["value"] == ("active", "completed")
        assert result[0]["comparator"] == "IN"

    def test_attribute_invalid_value_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected quoted string value for attribute"
        ):
            SearchExperimentsUtils.parse_search_filter("name = 42")

    def test_invalid_comparator_for_metric_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid comparator"):
            SearchExperimentsUtils.parse_search_filter("metric.acc LIKE 0.9")

    def test_parse_search_filter_multiple_statements_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchExperimentsUtils.parse_search_filter('name = "a"; name = "b"')

    def test_build_sql_order_by_param(self) -> None:
        clause = SearchExperimentsUtils._build_sql_order_by(["param.lr DESC"])
        assert clause == "ORDER BY json_extract(static_params, '$.lr') DESC"

    def test_build_sql_order_by_metric(self) -> None:
        clause = SearchExperimentsUtils._build_sql_order_by(["metric.acc ASC"])
        assert clause == "ORDER BY json_extract(dynamic_params, '$.acc') ASC"

    def test_build_sql_order_by_invalid_entity_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid order_by entity type"):
            SearchExperimentsUtils._build_sql_order_by(["tags ASC"])

    def test_parse_order_by_invalid_format_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid order_by clause"):
            SearchExperimentsUtils.parse_order_by("name ASC EXTRA")


class TestSearchEvalsUtilsBranches:
    """Cover SearchEvalsUtils edge cases and SQL generation branches."""

    def test_annotations_feedback_kind_dot_syntax(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations.feedback.quality = "true"'
        )
        assert result[0]["type"] == "annotation"
        assert result[0]["kind"] == "feedback"
        assert result[0]["key"] == "quality"

    def test_annotations_expectations_dot_syntax(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations.expectations.score = "high"'
        )
        assert result[0]["kind"] == "expectation"

    def test_annotations_no_kind_dot_syntax(self) -> None:
        result = SearchEvalsUtils.parse_search_filter('annotations.score = "high"')
        assert result[0]["kind"] is None
        assert result[0]["key"] == "score"

    def test_annotations_underscore_feedback(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations_feedback.quality = "true"'
        )
        assert result[0]["kind"] == "feedback"
        assert result[0]["key"] == "quality"

    def test_annotations_underscore_expectations(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations_expectations.score = "ok"'
        )
        assert result[0]["kind"] == "expectation"

    def test_annotations_underscore_expectation_singular(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations_expectation.score = "ok"'
        )
        assert result[0]["kind"] == "expectation"

    def test_json_boolean_value(self) -> None:
        result = SearchEvalsUtils.parse_search_filter("metadata.is_valid = true")
        # "true" preprocessed to 1 → numeric
        assert result[0]["value"] in (1.0, True)

    def test_invalid_field_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid field prefix"):
            SearchEvalsUtils.parse_search_filter('unknown_col.key = "x"')

    def test_invalid_attribute_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid attribute"):
            SearchEvalsUtils.parse_search_filter('totally_bogus = "x"')

    def test_invalid_comparator_date_attribute(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid comparator"):
            SearchEvalsUtils.parse_search_filter('created_at LIKE "2024-01-01"')

    def test_to_sql_with_grouped_and(self) -> None:
        w, p = SearchEvalsUtils.to_sql('(id = "a" AND dataset_id = "b") OR id = "c"')
        assert "(id = ? AND dataset_id = ?)" in w
        assert "OR" in w
        assert p == ["a", "b", "c"]

    def test_json_field_ilike(self) -> None:
        w, p = SearchEvalsUtils.to_sql('outputs.prediction ILIKE "%bert%"')
        assert w == "UPPER(json_extract(outputs, '$.prediction')) LIKE UPPER(?)"
        assert p == ["%bert%"]

    def test_json_field_in_with_list(self) -> None:
        w, p = SearchEvalsUtils.to_sql('scores.label IN ("a", "b")')
        assert "json_extract(scores, '$.label') IN (?,?)" in w
        assert p == ["a", "b"]

    def test_json_field_not_in_with_list(self) -> None:
        w, p = SearchEvalsUtils.to_sql('scores.label NOT IN ("a", "b")')
        assert "json_extract(scores, '$.label') NOT IN (?,?)" in w
        assert p == ["a", "b"]

    def test_attribute_id_ilike(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id ILIKE "%foo%"')
        assert w == "UPPER(id) LIKE UPPER(?)"
        assert p == ["%foo%"]

    def test_attribute_id_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id IN ("a", "b")')
        assert "id IN (?,?)" in w
        assert p == ["a", "b"]

    def test_attribute_id_not_in(self) -> None:
        w, p = SearchEvalsUtils.to_sql('id NOT IN ("a", "b")')
        assert "id NOT IN (?,?)" in w
        assert p == ["a", "b"]

    def test_date_invalid_token_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Expected ISO date string"):
            SearchEvalsUtils.parse_search_filter("created_at = (1, 2)")

    def test_attribute_invalid_value_raises(self) -> None:
        with pytest.raises(
            LumlFilterError, match="Expected string value for attribute"
        ):
            SearchEvalsUtils.parse_search_filter("id = 42")

    def test_parse_multiple_statements_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchEvalsUtils.parse_search_filter('id = "a"; id = "b"')


class TestSearchTracesUtilsBranches:
    """Cover SearchTracesUtils edge cases."""

    def test_invalid_bare_field_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid field"):
            SearchTracesUtils.parse_search_filter('totally_bogus = "x"')

    def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid field prefix"):
            SearchTracesUtils.parse_search_filter('foo.bar = "x"')

    def test_annotations_no_kind(self) -> None:
        result = SearchTracesUtils.parse_search_filter('annotations.quality = "ok"')
        assert result[0]["kind"] is None
        assert result[0]["key"] == "quality"

    def test_annotations_kind_dot(self) -> None:
        result = SearchTracesUtils.parse_search_filter(
            'annotations.feedback.quality = "ok"'
        )
        assert result[0]["kind"] == "feedback"
        assert result[0]["key"] == "quality"

    def test_annotations_expectations_dot(self) -> None:
        result = SearchTracesUtils.parse_search_filter(
            'annotations.expectations.q = "ok"'
        )
        assert result[0]["kind"] == "expectation"

    def test_state_named_value_ok(self) -> None:
        w, p = SearchTracesUtils.to_sql('state = "ok"')
        assert "state = ?" in w
        assert p == [1]

    def test_state_named_value_error(self) -> None:
        w, p = SearchTracesUtils.to_sql('state = "error"')
        assert p == [2]

    def test_state_named_value_in_progress(self) -> None:
        w, p = SearchTracesUtils.to_sql('state = "in_progress"')
        assert p == [3]

    def test_state_named_value_unspecified(self) -> None:
        w, p = SearchTracesUtils.to_sql('state = "state_unspecified"')
        assert p == [0]

    def test_state_invalid_name_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid state value"):
            SearchTracesUtils.parse_search_filter('state = "totally_invalid"')

    def test_state_numeric_value(self) -> None:
        w, p = SearchTracesUtils.to_sql("state = 2")
        assert p == [2]

    def test_state_in_with_named_list(self) -> None:
        w, p = SearchTracesUtils.to_sql('state IN ("ok", "error")')
        assert "state IN (?,?)" in w
        assert p == [1, 2]

    def test_state_not_in_with_named_list(self) -> None:
        w, p = SearchTracesUtils.to_sql('state NOT IN ("ok", "error")')
        assert "state NOT IN (?,?)" in w
        assert p == [1, 2]

    def test_state_invalid_value_token_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.parse_search_filter("state = ?")

    def test_created_at_string(self) -> None:
        w, p = SearchTracesUtils.to_sql('created_at > "2024-01-01"')
        assert "created_at > ?" in w
        assert p == ["2024-01-01"]

    def test_created_at_invalid_value_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Expected ISO date string"):
            SearchTracesUtils.parse_search_filter("created_at = (1, 2)")

    def test_execution_time_numeric(self) -> None:
        w, p = SearchTracesUtils.to_sql("execution_time > 1000")
        assert "execution_time > ?" in w
        assert p == [1000]

    def test_span_count_numeric(self) -> None:
        w, p = SearchTracesUtils.to_sql("span_count >= 5")
        assert "span_count >= ?" in w
        assert p == [5.0]

    def test_trace_id_ilike(self) -> None:
        w, p = SearchTracesUtils.to_sql('trace_id ILIKE "%abc%"')
        assert w == "UPPER(trace_id) LIKE UPPER(?)"
        assert p == ["%abc%"]

    def test_trace_id_in_list(self) -> None:
        w, p = SearchTracesUtils.to_sql('trace_id IN ("a", "b")')
        assert "trace_id IN (?,?)" in w
        assert p == ["a", "b"]

    def test_trace_id_not_in_list(self) -> None:
        w, p = SearchTracesUtils.to_sql('trace_id NOT IN ("a", "b")')
        assert "trace_id NOT IN (?,?)" in w
        assert p == ["a", "b"]

    def test_evals_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals = "eval-1"')
        assert "SELECT DISTINCT trace_id FROM eval_traces_bridge" in w
        assert "eval_id = ?" in w
        assert p == ["eval-1"]

    def test_evals_neq(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals != "eval-1"')
        assert "trace_id NOT IN" in w
        assert p == ["eval-1"]

    def test_evals_ilike(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals ILIKE "%foo%"')
        assert "UPPER(eval_id) LIKE UPPER(?)" in w
        assert p == ["%foo%"]

    def test_evals_like(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals LIKE "%foo%"')
        assert "eval_id LIKE ?" in w
        assert p == ["%foo%"]

    def test_evals_in(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals IN ("a", "b")')
        assert "eval_id IN (?,?)" in w
        assert p == ["a", "b"]

    def test_evals_not_in(self) -> None:
        w, p = SearchTracesUtils.to_sql('evals NOT IN ("a", "b")')
        assert "trace_id NOT IN" in w
        assert "eval_id IN (?,?)" in w
        assert p == ["a", "b"]

    def test_span_attributes_eq(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.http.method = "GET"')
        assert "json_extract(attributes" in w
        assert p == ["GET"]

    def test_span_attributes_ilike(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.url ILIKE "%api%"')
        assert "UPPER(" in w
        assert p == ["%api%"]

    def test_span_attributes_in(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.code IN ("200", "201")')
        assert "IN (?,?)" in w
        assert p == ["200", "201"]

    def test_span_attributes_not_in(self) -> None:
        w, p = SearchTracesUtils.to_sql('attributes.code NOT IN ("500", "503")')
        assert "NOT IN (?,?)" in w
        assert p == ["500", "503"]

    def test_invalid_numeric_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid comparator"):
            SearchTracesUtils.parse_search_filter('execution_time LIKE "1"')

    def test_invalid_state_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid comparator"):
            SearchTracesUtils.parse_search_filter('state > "ok"')

    def test_evals_invalid_comparator_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid comparator"):
            SearchTracesUtils.parse_search_filter("evals > 1")

    def test_multiple_statements_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchTracesUtils.parse_search_filter('trace_id = "a"; trace_id = "b"')


class TestSearchUtilsBaseExtras:
    def test_join_in_truncated_tokens(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid clause"):
            SearchExperimentsUtils.parse_search_filter("status IN")

    def test_join_in_not_in_without_parenthesis_extends(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchExperimentsUtils.parse_search_filter("status NOT IN status")

    def test_validate_comparison_wrong_token_count_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="Expected 3 tokens"):
            SearchUtils._validate_comparison([1, 2])

    def test_validate_comparison_non_identifier_left_raises(self) -> None:
        class _Fake:
            pass

        with pytest.raises(LumlFilterError, match="Expected 'Identifier'"):
            SearchUtils._validate_comparison([_Fake(), _Fake(), _Fake()])

    def test_base_get_identifier_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            SearchUtils._get_identifier("x", set())

    def test_base_get_value_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            SearchUtils._get_value("attribute", "k", None)  # type: ignore[arg-type]

    def test_base_parse_search_filter_empty_returns_empty(self) -> None:
        assert SearchUtils.parse_search_filter(None) == []
        assert SearchUtils.parse_search_filter("") == []

    def test_base_parse_search_filter_propagates_via_subclass(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchExperimentsUtils.parse_search_filter('name = "a"; status = "b"')

    def test_preprocess_backticks_annotation_key_with_spaces(self) -> None:
        result = SearchEvalsUtils.parse_search_filter(
            'annotations.feedback.quality assessment = "ok"'
        )
        assert result[0]["type"] == "annotation"
        assert result[0]["key"] == "quality assessment"

    def test_invalid_attribute_via_attribute_prefix(self) -> None:
        with pytest.raises(LumlFilterError, match="Invalid attribute key"):
            SearchExperimentsUtils.parse_search_filter('attribute.unknown = "x"')

    def test_experiments_invalid_identifier_type_in_get_comparison(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchExperimentsUtils.parse_search_filter('totally.bogus = "x"')


class TestSearchEvalsUtilsExtras:
    def test_json_boolean_token_via_underscore_form(self) -> None:
        result = SearchEvalsUtils.parse_search_filter("scores.flag = true")
        assert result is not None

    def test_date_attribute_numeric_value_accepted(self) -> None:
        result = SearchEvalsUtils.parse_search_filter("created_at > 1700000000")
        assert result[0]["key"] == "created_at"

    def test_invalid_comparator_annotation_with_kind_shows_field(self) -> None:
        with pytest.raises(LumlFilterError, match="annotations.feedback.quality"):
            SearchEvalsUtils.parse_search_filter(
                "annotations.feedback.quality BETWEEN 1 AND 2"
            )


class TestSearchTracesUtilsExtras:
    def test_resolve_state_value_integer_passthrough(self) -> None:
        assert SearchTracesUtils._resolve_state_value(2) == 2

    def test_date_column_numeric_passthrough(self) -> None:
        result = SearchTracesUtils.parse_search_filter("created_at > 1700000000")
        assert result[0]["key"] == "created_at"

    def test_grouped_filter_in_build_sql(self) -> None:
        w, p = SearchTracesUtils.to_sql(
            '(trace_id = "a" AND state = "ok") OR span_count > 5'
        )
        assert "(trace_id = ? AND state = ?)" in w
        assert "OR" in w

    def test_trace_id_eq_comparator(self) -> None:
        w, p = SearchTracesUtils.to_sql('trace_id = "abc"')
        assert "trace_id = ?" in w
        assert p == ["abc"]

    def test_trace_id_neq_comparator(self) -> None:
        w, p = SearchTracesUtils.to_sql('trace_id != "abc"')
        assert "trace_id != ?" in w
        assert p == ["abc"]

    def test_state_invalid_token_type_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchTracesUtils.parse_search_filter("state = ?")

    def test_multiple_statements_in_traces_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchTracesUtils.parse_search_filter('trace_id = "a"; trace_id = "b"')


class TestJoinInTokensFourthNone:
    def test_three_token_not_in_truncated(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchExperimentsUtils.parse_search_filter("name NOT IN")


class TestSearchUtilsBaseGetComparison:
    def test_covers_lines_286_292(self) -> None:
        import sqlparse
        from sqlparse.sql import Comparison as SqlComparison

        class _Concrete(SearchUtils):
            VALID_SEARCH_ATTRIBUTE_KEYS: set = {"name"}

            @classmethod
            def _get_identifier(cls, raw: str, valid: set) -> dict:  # type: ignore[override]
                return {"type": "attribute", "key": raw.strip()}

            @classmethod
            def _get_value(cls, identifier_type: str, key: str, token: Any) -> str:  # type: ignore[override]  # noqa: ANN401
                return token.value.strip("'\"")

        parsed = sqlparse.parse('name = "bert"')
        comparison = next(t for t in parsed[0].tokens if isinstance(t, SqlComparison))
        result = _Concrete._get_comparison(comparison)
        assert result["key"] == "name"
        assert result["comparator"] == "="
        assert result["value"] == "bert"


class TestSearchUtilsBaseParseSearchFilterEdges:
    def test_non_empty_propagates_to_process_statement(self) -> None:
        with pytest.raises((AttributeError, NotImplementedError)):
            SearchUtils.parse_search_filter('name = "bert"')

    def test_multiple_statements_raises(self) -> None:
        with pytest.raises(LumlFilterError, match="multiple expressions"):
            SearchUtils.parse_search_filter('name = "a"; name = "b"')

    def test_sqlparse_exception_wraps(self) -> None:
        from unittest.mock import patch

        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                side_effect=Exception("parse fail"),
            ),
            pytest.raises(LumlFilterError, match="Error on parsing filter"),
        ):
            SearchUtils.parse_search_filter("something")

    def test_empty_parse_result_raises(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                return_value=[],
            ),
            pytest.raises(LumlFilterError, match="Could not be parsed"),
        ):
            SearchUtils.parse_search_filter("something")


class TestSearchExperimentsValidateFilterString:
    def test_validate_none_passes(self) -> None:
        SearchExperimentsUtils.validate_filter_string(None)

    def test_validate_valid_filter_passes(self) -> None:
        SearchExperimentsUtils.validate_filter_string('name LIKE "%bert%"')

    def test_validate_invalid_filter_raises(self) -> None:
        with pytest.raises(LumlFilterError):
            SearchExperimentsUtils.validate_filter_string('nonexistent = "x"')


class TestSearchExperimentsUtilsDirectCalls:
    def test_tag_dot_notation_covers_line_457(self) -> None:
        result = SearchExperimentsUtils.parse_search_filter('tag.name LIKE "%bert%"')
        assert result[0]["type"] == "tag"
        assert result[0]["key"] == "name"

    def test_get_value_param_boolean_true_covers_line_502(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "TRUE")
        result = SearchExperimentsUtils._get_value("param", "enabled", bool_token)
        assert result is True

    def test_get_value_param_boolean_false(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "FALSE")
        result = SearchExperimentsUtils._get_value("param", "flag", bool_token)
        assert result is False

    def test_get_value_unknown_type_raises_line_543(self) -> None:
        str_token = SqlToken(TokenType.Literal.String.Single, "'val'")
        with pytest.raises(LumlFilterError, match="Invalid identifier type"):
            SearchExperimentsUtils._get_value("unknown_type", "key", str_token)

    def test_parse_filter_sqlparse_exception_covers_611_612(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                side_effect=Exception("boom"),
            ),
            pytest.raises(LumlFilterError, match="Error on parsing filter"),
        ):
            SearchExperimentsUtils.parse_search_filter('name = "a"')

    def test_parse_filter_empty_result_covers_614(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                return_value=[],
            ),
            pytest.raises(LumlFilterError, match="Could not be parsed"),
        ):
            SearchExperimentsUtils.parse_search_filter('name = "a"')


class TestSearchEvalsUtilsDirectCalls:
    def test_get_json_value_boolean_true_covers(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "TRUE")
        result = SearchEvalsUtils._get_json_value("flag", bool_token)
        assert result is True

    def test_get_json_value_boolean_false(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "FALSE")
        result = SearchEvalsUtils._get_json_value("active", bool_token)
        assert result is False

    def test_invalid_comparator_annotation_with_kind_covers(self) -> None:
        # <> is not in VALID_ANNOTATION_COMPARATORS; with kind="feedback"
        # field = "annotations.feedback.quality"
        with pytest.raises(LumlFilterError, match="annotations.feedback.quality"):
            SearchEvalsUtils.parse_search_filter(
                'annotations.feedback.quality <> "bad"'
            )

    def test_invalid_comparator_annotation_no_kind(self) -> None:
        # Annotation without kind: field = "annotations.<key>"
        with pytest.raises(LumlFilterError, match="annotations.score"):
            SearchEvalsUtils.parse_search_filter('annotations.score <> "bad"')

    def test_parse_filter_sqlparse_exception_covers(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                side_effect=Exception("boom"),
            ),
            pytest.raises(LumlFilterError, match="Error on parsing filter"),
        ):
            SearchEvalsUtils.parse_search_filter('id = "a"')

    def test_parse_filter_empty_result_covers(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                return_value=[],
            ),
            pytest.raises(LumlFilterError, match="Could not be parsed"),
        ):
            SearchEvalsUtils.parse_search_filter('id = "a"')

    def test_get_json_value_unknown_token_raises_line_887(self) -> None:
        null_token = SqlToken(TokenType.Keyword, "NULL")
        with pytest.raises(LumlFilterError, match="Expected string or numeric value"):
            SearchEvalsUtils._get_json_value("flag", null_token)


class TestSearchTracesUtilsDirectCalls:
    def test_get_value_boolean_true_covers_1266_1268(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "TRUE")
        result = SearchTracesUtils._get_value("trace_column", "trace_id", bool_token)
        assert result is True

    def test_get_value_boolean_false(self) -> None:
        bool_token = SqlToken(TokenType.Keyword, "FALSE")
        result = SearchTracesUtils._get_value("trace_column", "trace_id", bool_token)
        assert result is False

    def test_parse_filter_sqlparse_exception_covers_1437_1438(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                side_effect=Exception("boom"),
            ),
            pytest.raises(LumlFilterError, match="Error on parsing filter"),
        ):
            SearchTracesUtils.parse_search_filter('trace_id = "a"')

    def test_parse_filter_empty_result_covers_1440(self) -> None:
        with (
            patch(
                "luml.experiments.backends._search_utils.sqlparse.parse",
                return_value=[],
            ),
            pytest.raises(LumlFilterError, match="Could not be parsed"),
        ):
            SearchTracesUtils.parse_search_filter('trace_id = "a"')

    def test_get_value_unknown_token_raises_line_1268(self) -> None:
        null_token = SqlToken(TokenType.Keyword, "NULL")
        with pytest.raises(LumlFilterError, match="Expected string or numeric value"):
            SearchTracesUtils._get_value("trace_column", "trace_id", null_token)
