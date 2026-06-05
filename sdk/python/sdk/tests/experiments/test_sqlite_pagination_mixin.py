import pytest

from luml.experiments.backends._sqlite_pagination_mixin import SQLitePaginationMixin


class TestParseValue:
    def test_valid_json_object_parsed(self) -> None:
        result = SQLitePaginationMixin._parse_value('{"a": 1}')
        assert result == {"a": 1}

    def test_valid_json_array_parsed(self) -> None:
        result = SQLitePaginationMixin._parse_value("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_invalid_json_returns_raw_string(self) -> None:
        # lines 15-16: JSONDecodeError → return original string
        raw = "{not valid json"
        result = SQLitePaginationMixin._parse_value(raw)
        assert result == raw

    def test_invalid_json_array_returns_raw_string(self) -> None:
        raw = "[broken"
        result = SQLitePaginationMixin._parse_value(raw)
        assert result == raw

    def test_plain_string_returned_as_is(self) -> None:
        assert SQLitePaginationMixin._parse_value("hello") == "hello"

    def test_non_string_returned_as_is(self) -> None:
        assert SQLitePaginationMixin._parse_value(42) == 42
        assert SQLitePaginationMixin._parse_value(None) is None


class TestBuildSortExpr:
    def test_json_sort_column_valid_sort_by(self) -> None:
        result = SQLitePaginationMixin._build_sort_expr("score", "dynamic_params")
        assert result == "json_extract(dynamic_params, '$.score')"

    def test_json_sort_column_invalid_sort_by_raises(self) -> None:
        # line 36: sort_by contains invalid characters → ValueError
        with pytest.raises(ValueError, match="sort_by must match pattern"):
            SQLitePaginationMixin._build_sort_expr("my.field", "scores_col")

    def test_json_sort_column_empty_sort_by_raises(self) -> None:
        with pytest.raises(ValueError, match="sort_by must match pattern"):
            SQLitePaginationMixin._build_sort_expr("", "scores_col")

    def test_plain_sort_by_no_allowed_columns(self) -> None:
        assert SQLitePaginationMixin._build_sort_expr("name", None) == "name"

    def test_sort_by_not_in_allowed_falls_back_to_created_at(self) -> None:
        # line 41: unknown sort_by → fallback to created_at
        result = SQLitePaginationMixin._build_sort_expr(
            "unknown_col", None, {"name", "created_at"}
        )
        assert result == "created_at"

    def test_sort_by_in_allowed_returned_unchanged(self) -> None:
        result = SQLitePaginationMixin._build_sort_expr(
            "name", None, {"name", "created_at"}
        )
        assert result == "name"


class TestBuildCursorClause:
    def test_no_cursor_returns_empty(self) -> None:
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "created_at", "asc", cursor_id=None, cursor_value=None
        )
        assert clause == ""
        assert params == []

    def test_cursor_id_only_no_value_covers_line_80(self) -> None:
        # line 80: cursor_id set, cursor_value=None → id-only WHERE clause
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "created_at", "asc", cursor_id="abc-123", cursor_value=None
        )
        assert "id > ?" in clause
        assert params == ["abc-123"]

    def test_cursor_id_only_desc_order(self) -> None:
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "created_at", "desc", cursor_id="abc-123", cursor_value=None
        )
        assert "id < ?" in clause
        assert params == ["abc-123"]

    def test_cursor_with_value_asc(self) -> None:
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "name", "asc", cursor_id="row-1", cursor_value="alpha"
        )
        assert "name > ?" in clause
        assert params == ["alpha", "alpha", "row-1"]

    def test_cursor_with_datetime_column_wraps_datetime(self) -> None:
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "created_at", "asc", cursor_id="row-1", cursor_value="2024-01-01"
        )
        assert "datetime(created_at)" in clause
        assert "datetime(?)" in clause

    def test_cursor_custom_id_column(self) -> None:
        clause, params = SQLitePaginationMixin._build_cursor_clause(
            "name", "asc", cursor_id="row-1", cursor_value=None, id_column="eval_id"
        )
        assert "eval_id > ?" in clause


class TestExtractCursorValue:
    def test_plain_column_extracted(self) -> None:
        # line 145: no json_sort_column
        columns = ["id", "name", "created_at"]
        row = ("row-1", "bert", "2024-01-01")
        result = SQLitePaginationMixin._extract_cursor_value(row, columns, "name")
        assert result == "bert"

    def test_json_sort_column_extracts_nested_key(self) -> None:
        # lines 142-144: json_sort_column set
        columns = ["id", "scores"]
        row = ("row-1", '{"accuracy": 0.95}')
        result = SQLitePaginationMixin._extract_cursor_value(
            row, columns, "accuracy", json_sort_column="scores"
        )
        assert result == 0.95

    def test_json_sort_column_missing_key_returns_none(self) -> None:
        columns = ["id", "scores"]
        row = ("row-1", '{"f1": 0.8}')
        result = SQLitePaginationMixin._extract_cursor_value(
            row, columns, "accuracy", json_sort_column="scores"
        )
        assert result is None

    def test_json_sort_column_null_raw_returns_none(self) -> None:
        # line 143: col_raw is None/empty → {} → .get() → None
        columns = ["id", "scores"]
        row = ("row-1", None)
        result = SQLitePaginationMixin._extract_cursor_value(
            row, columns, "accuracy", json_sort_column="scores"
        )
        assert result is None
