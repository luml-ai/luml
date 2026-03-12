# flake8: noqa: E501

import pytest

from luml.experiments.backends._exceptions import LumlFilterError
from luml.experiments.backends._search_utils import SearchExperimentsUtils

# ---------------------------------------------------------------------------
# parse_search_filter — parsed dict structure
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# to_sql — WHERE clause generation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# to_sql — ORDER BY clause generation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# parse_order_by — returns (type, key, is_ascending)
# ---------------------------------------------------------------------------


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
