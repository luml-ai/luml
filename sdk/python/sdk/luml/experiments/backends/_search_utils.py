# flake8: noqa: E501

import operator
import re
from typing import Any

import sqlparse
from sqlparse.sql import (
    Comparison,
    Identifier,
    Parenthesis,
    Statement,
    Token,
    TokenList,
)
from sqlparse.tokens import Token as TokenType

from luml.experiments.backends._exceptions import LumlFilterError


def _convert_like_pattern_to_regex(pattern: str, flags: int = 0) -> re.Pattern:
    if not pattern.startswith("%"):
        pattern = "^" + pattern
    if not pattern.endswith("%"):
        pattern = pattern + "$"
    return re.compile(pattern.replace("_", ".").replace("%", ".*"), flags)


def _like(string: str, pattern: str) -> bool:
    return _convert_like_pattern_to_regex(pattern).match(string) is not None


def _ilike(string: str, pattern: str) -> bool:
    return (
        _convert_like_pattern_to_regex(pattern, flags=re.IGNORECASE).match(string)
        is not None
    )


def _join_in_comparison_tokens(tokens: list) -> list:
    """
    Find IN / NOT IN token sequences and join them into a single Comparison token.
    Requires sqlparse >= 0.4.4.
    """
    non_whitespace_tokens = [t for t in tokens if not t.is_whitespace]
    joined_tokens = []
    num_tokens = len(non_whitespace_tokens)
    iterator = enumerate(non_whitespace_tokens)
    while elem := next(iterator, None):
        index, first = elem
        # We need at least 3 tokens to form an IN comparison or a NOT IN comparison
        if num_tokens - index < 3:
            joined_tokens.extend(non_whitespace_tokens[index:])
            break

        # Wait until we encounter an identifier token
        if not isinstance(first, Identifier):
            joined_tokens.append(first)
            continue

        (_, second) = next(iterator)
        (_, third) = next(iterator)

        # IN
        if (
            isinstance(first, Identifier)
            and second.match(ttype=TokenType.Keyword, values=["IN"])
            and isinstance(third, Parenthesis)
        ):
            joined_tokens.append(Comparison(TokenList([first, second, third])))
            continue

        (_, fourth) = next(iterator, (None, None))
        if fourth is None:
            joined_tokens.extend([first, second, third])
            break

        # NOT IN
        if (
            isinstance(first, Identifier)
            and second.match(ttype=TokenType.Keyword, values=["NOT"])
            and third.match(ttype=TokenType.Keyword, values=["IN"])
            and isinstance(fourth, Parenthesis)
        ):
            joined_tokens.append(
                Comparison(
                    TokenList([first, Token(TokenType.Keyword, "NOT IN"), fourth])
                )
            )
            continue

        joined_tokens.extend([first, second, third, fourth])

    return joined_tokens


class SearchUtils:
    LIKE_OPERATOR = "LIKE"
    ILIKE_OPERATOR = "ILIKE"
    ASC_OPERATOR = "asc"
    DESC_OPERATOR = "desc"
    VALID_ORDER_BY_TAGS = [ASC_OPERATOR, DESC_OPERATOR]
    VALID_METRIC_COMPARATORS = {">", ">=", "!=", "=", "<", "<="}
    VALID_PARAM_COMPARATORS = {"!=", "=", LIKE_OPERATOR, ILIKE_OPERATOR}
    VALID_TAG_COMPARATORS = {"!=", "=", LIKE_OPERATOR, ILIKE_OPERATOR}
    VALID_STRING_ATTRIBUTE_COMPARATORS = {
        "!=",
        "=",
        LIKE_OPERATOR,
        ILIKE_OPERATOR,
        "IN",
        "NOT IN",
    }
    VALID_NUMERIC_ATTRIBUTE_COMPARATORS = VALID_METRIC_COMPARATORS
    NUMERIC_ATTRIBUTES: set[str] = set()
    STRING_VALUE_TYPES = {TokenType.Literal.String.Single}
    DELIMITER_VALUE_TYPES = {TokenType.Punctuation}
    WHITESPACE_VALUE_TYPE = TokenType.Text.Whitespace
    NUMERIC_VALUE_TYPES = {
        TokenType.Literal.Number.Integer,
        TokenType.Literal.Number.Float,
    }

    _METRIC_IDENTIFIER = "metric"
    _PARAM_IDENTIFIER = "param"
    _TAG_IDENTIFIER = "tag"
    _ATTRIBUTE_IDENTIFIER = "attribute"

    @staticmethod
    def get_comparison_func(comparator: str):  # noqa: ANN205
        return {
            ">": operator.gt,
            ">=": operator.ge,
            "=": operator.eq,
            "!=": operator.ne,
            "<=": operator.le,
            "<": operator.lt,
            "LIKE": _like,
            "ILIKE": _ilike,
            "IN": lambda x, y: x in y,
            "NOT IN": lambda x, y: x not in y,
        }[comparator]

    @classmethod
    def _trim_ends(cls, string_value: str) -> str:
        return string_value[1:-1]

    @classmethod
    def _is_quoted(cls, value: str, pattern: str) -> bool:
        return len(value) >= 2 and value.startswith(pattern) and value.endswith(pattern)

    @classmethod
    def _trim_backticks(cls, entity_type: str) -> str:
        """Remove backticks from identifier like `param`, if they exist."""
        if cls._is_quoted(entity_type, "`"):
            return cls._trim_ends(entity_type)
        return entity_type

    @classmethod
    def _strip_quotes(cls, value: str, expect_quoted_value: bool = False) -> str:
        """
        Remove quotes for input string.
        Values of type strings are expected to have quotes.
        Keys containing special characters are also expected to be enclosed in quotes.
        """
        if cls._is_quoted(value, "'") or cls._is_quoted(value, '"'):
            return cls._trim_ends(value)
        if expect_quoted_value:
            raise LumlFilterError(
                "Parameter value is either not quoted or unidentified quote "
                f"types used for string value {value}. Use either single or double quotes."
            )
        return value

    @classmethod
    def _validate_comparison(cls, tokens: list) -> None:
        base_error_string = "Invalid comparison clause"
        if len(tokens) != 3:
            raise LumlFilterError(
                f"{base_error_string}. Expected 3 tokens found {len(tokens)}"
            )
        if not isinstance(tokens[0], Identifier):
            raise LumlFilterError(
                f"{base_error_string}. Expected 'Identifier' found '{tokens[0]}'"
            )

    @classmethod
    def _check_valid_identifier_list(cls, tup: tuple[Any, ...]) -> None:
        if len(tup) == 0:
            raise LumlFilterError(
                "While parsing a list in the query,"
                " expected a non-empty list of string values, but got empty list"
            )
        if not all(isinstance(x, str) for x in tup):
            raise LumlFilterError(
                "While parsing a list in the query, expected string value, punctuation, "
                f"or whitespace, but got different type in list: {tup}"
            )

    @classmethod
    def _parse_list_from_sql_token(cls, token: Token) -> tuple:
        import ast

        try:
            parsed = ast.literal_eval(token.value)
        except SyntaxError as e:
            raise LumlFilterError(
                "While parsing a list in the query,"
                " expected a non-empty list of string values, but got ill-formed list."
            ) from e

        parsed = parsed if isinstance(parsed, tuple) else (parsed,)
        cls._check_valid_identifier_list(parsed)
        return parsed

    @classmethod
    def _get_identifier(cls, identifier_str: str, valid_attributes: set) -> Any:  # noqa: ANN401
        raise NotImplementedError

    @classmethod
    def _get_value(cls, identifier_type: str, key: str, token: Token) -> Any:  # noqa: ANN401
        raise NotImplementedError

    @classmethod
    def _get_comparison(cls, comparison: Comparison) -> dict:
        stripped = [token for token in comparison.tokens if not token.is_whitespace]
        cls._validate_comparison(stripped)
        left, comparator_token, right = stripped
        comp = cls._get_identifier(left.value, cls.VALID_SEARCH_ATTRIBUTE_KEYS)  # type: ignore[attr-defined]
        comp["comparator"] = comparator_token.value.upper()
        comp["value"] = cls._get_value(comp["type"], comp["key"], right)
        return comp

    @classmethod
    def _process_token_list(cls, tokens: list) -> list[dict]:
        tokens = _join_in_comparison_tokens(tokens)
        invalids = [
            token
            for token in tokens
            if not (
                isinstance(token, Comparison | Parenthesis)
                or token.is_whitespace
                or token.match(ttype=TokenType.Keyword, values=["AND", "OR"])
            )
        ]
        if invalids:
            invalid_clauses = ", ".join(f"'{token}'" for token in invalids)
            raise LumlFilterError(
                f"Invalid clause(s) in filter string: {invalid_clauses}"
            )
        result = []
        for token in tokens:
            if token.is_whitespace:
                continue
            if token.match(ttype=TokenType.Keyword, values=["AND"]):
                result.append({"operator": "AND"})
            elif token.match(ttype=TokenType.Keyword, values=["OR"]):
                result.append({"operator": "OR"})
            elif isinstance(token, Parenthesis):
                # token.tokens[0] = '(', token.tokens[-1] = ')' — strip them
                inner = cls._process_token_list(token.tokens[1:-1])
                result.append({"group": inner})
            elif isinstance(token, Comparison):
                result.append(cls._get_comparison(token))
        return result

    @classmethod
    def _process_statement(cls, statement: Statement) -> list[dict]:
        return cls._process_token_list(statement.tokens)

    @staticmethod
    def _preprocess_filter(filter_string: str) -> str:
        """Convert CONTAINS operator to LIKE with % wildcards."""

        def replace_contains(m: re.Match) -> str:
            quote = m.group(1)
            val = m.group(2)
            if not val.startswith("%"):
                val = "%" + val
            if not val.endswith("%"):
                val = val + "%"
            return f"LIKE {quote}{val}{quote}"

        return re.sub(
            r"\bCONTAINS\b\s+([\"'])(.+?)\1",
            replace_contains,
            filter_string,
            flags=re.IGNORECASE,
        )

    @classmethod
    def parse_search_filter(cls, filter_string: str | None) -> list[dict]:
        if not filter_string:
            return []
        try:
            parsed = sqlparse.parse(filter_string)
        except Exception as e:
            raise LumlFilterError(f"Error on parsing filter '{filter_string}'") from e
        if len(parsed) == 0 or not isinstance(parsed[0], Statement):
            raise LumlFilterError(
                f"Invalid filter '{filter_string}'. Could not be parsed."
            )
        if len(parsed) > 1:
            raise LumlFilterError(
                f"Search filter contained multiple expressions {filter_string!r}. "
                "Provide AND-ed expression list."
            )
        return cls._process_statement(parsed[0])


class SearchExperimentsUtils(SearchUtils):
    VALID_SEARCH_ATTRIBUTE_KEYS = {
        "id",
        "name",
        "status",
        "created_at",
        "duration",
        "description",
        "group_id",
    }
    VALID_ORDER_BY_ATTRIBUTE_KEYS = {"name", "status", "created_at", "duration", "id"}
    NUMERIC_ATTRIBUTES = {"duration", "created_at"}
    STRING_ATTRIBUTES = {"id", "name", "status", "description", "group_id"}

    # Identifier type constants
    _ATTRIBUTE_IDENTIFIER = "attribute"
    _TAG_IDENTIFIER = "tag"
    _PARAM_IDENTIFIER = "param"
    _METRIC_IDENTIFIER = "metric"

    # Identifier aliases
    _PARAM_IDENTIFIERS = {"param", "params", "parameter", "parameters", "static_params"}
    _METRIC_IDENTIFIERS = {"metric", "metrics", "dynamic_params"}
    _TAG_IDENTIFIERS = {"tag", "tags"}
    _ATTRIBUTE_IDENTIFIERS = {"attribute", "attr"}

    @classmethod
    def _get_identifier(cls, identifier_str: str, valid_attributes: set) -> dict:
        """
        Parse an identifier string into a type/key dict.

        Examples:
            "name"              → {"type": "attribute", "key": "name"}
            "attribute.name"    → {"type": "attribute", "key": "name"}
            "tags"              → {"type": "tag",       "key": "tags"}
            "param.lr"          → {"type": "param",     "key": "lr"}
            "static_params.lr"  → {"type": "param",     "key": "lr"}
            "metric.acc"        → {"type": "metric",    "key": "acc"}
            "dynamic_params.acc"→ {"type": "metric",    "key": "acc"}
        """
        identifier_str = cls._trim_backticks(identifier_str.strip())
        parts = identifier_str.split(".", maxsplit=1)

        if len(parts) == 1:
            key = cls._trim_backticks(cls._strip_quotes(parts[0]))
            key_lower = key.lower()
            if key_lower in cls._TAG_IDENTIFIERS:
                return {"type": cls._TAG_IDENTIFIER, "key": key}
            entity_type = cls._ATTRIBUTE_IDENTIFIER
        else:
            entity_type_str, raw_key = parts
            entity_type_str_lower = entity_type_str.lower()
            key = cls._trim_backticks(cls._strip_quotes(raw_key))

            if entity_type_str_lower in cls._PARAM_IDENTIFIERS:
                entity_type = cls._PARAM_IDENTIFIER
            elif entity_type_str_lower in cls._METRIC_IDENTIFIERS:
                entity_type = cls._METRIC_IDENTIFIER
            elif entity_type_str_lower in cls._TAG_IDENTIFIERS:
                entity_type = cls._TAG_IDENTIFIER
            elif entity_type_str_lower in cls._ATTRIBUTE_IDENTIFIERS:
                entity_type = cls._ATTRIBUTE_IDENTIFIER
            else:
                raise LumlFilterError(
                    f"Invalid entity type '{entity_type_str}'. "
                    "Valid types are: attribute, tag, param/params/static_params, "
                    "metric/metrics/dynamic_params"
                )

        if entity_type == cls._ATTRIBUTE_IDENTIFIER and key not in valid_attributes:
            raise LumlFilterError(
                f"Invalid attribute key '{key}' specified. "
                f"Valid attribute keys are {sorted(valid_attributes)}. "
                "For dynamic metrics use: metric.<key> or dynamic_params.<key>. "
                "For static params use: param.<key> or static_params.<key>."
            )

        if entity_type in (
            cls._PARAM_IDENTIFIER,
            cls._METRIC_IDENTIFIER,
        ) and not re.match(r"^[a-zA-Z0-9_.-]+$", key):
            raise LumlFilterError(
                f"Invalid key {key!r} for {entity_type}. "
                "Keys may only contain alphanumeric characters, underscores, dots, and hyphens."
            )

        return {"type": entity_type, "key": key}

    @classmethod
    def _get_value(cls, identifier_type: str, key: str, token: Token) -> Any:  # noqa: ANN401, C901
        """Extract and validate the comparison value from a sqlparse token."""
        if identifier_type == cls._METRIC_IDENTIFIER:
            if token.ttype not in cls.NUMERIC_VALUE_TYPES:
                raise LumlFilterError(
                    f"Expected numeric value type for metric. Found {token.value!r}"
                )
            return float(token.value)

        if identifier_type == cls._PARAM_IDENTIFIER:
            if token.ttype in cls.NUMERIC_VALUE_TYPES:
                return float(token.value)
            if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
                return cls._strip_quotes(token.value, expect_quoted_value=True)
            raise LumlFilterError(
                f"Expected string or numeric value for param. Got {token.value!r}"
            )

        if identifier_type == cls._TAG_IDENTIFIER:
            if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
                return cls._strip_quotes(token.value, expect_quoted_value=True)
            raise LumlFilterError(
                f"Expected quoted string value for tag. Got {token.value!r}"
            )

        if identifier_type == cls._ATTRIBUTE_IDENTIFIER:
            if key == "duration":
                if token.ttype not in cls.NUMERIC_VALUE_TYPES:
                    raise LumlFilterError(
                        f"Expected numeric value for 'duration'. Got {token.value!r}"
                    )
                return float(token.value)
            if key == "created_at":
                # ISO date string or bare numeric
                if token.ttype in cls.STRING_VALUE_TYPES or isinstance(
                    token, Identifier
                ):
                    return cls._strip_quotes(token.value, expect_quoted_value=True)
                if token.ttype in cls.NUMERIC_VALUE_TYPES:
                    return token.value
                raise LumlFilterError(
                    f"Expected quoted date string for 'created_at'. Got {token.value!r}"
                )
            # String attributes (name, status, description, group_id)
            if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
                return cls._strip_quotes(token.value, expect_quoted_value=True)
            if isinstance(token, Parenthesis):
                return cls._parse_list_from_sql_token(token)
            raise LumlFilterError(
                f"Expected quoted string value for attribute '{key}'. Got {token.value!r}"
            )

        raise LumlFilterError(f"Invalid identifier type '{identifier_type}'")

    @classmethod
    def _get_comparison(cls, comparison: Comparison) -> dict:
        stripped = [token for token in comparison.tokens if not token.is_whitespace]
        cls._validate_comparison(stripped)
        left, comparator_token, right = stripped
        comp = cls._get_identifier(left.value, cls.VALID_SEARCH_ATTRIBUTE_KEYS)
        comparator = comparator_token.value.upper()

        if comp["type"] == cls._METRIC_IDENTIFIER:
            valid_comparators = cls.VALID_METRIC_COMPARATORS
        elif comp["type"] == cls._PARAM_IDENTIFIER:
            valid_comparators = cls.VALID_PARAM_COMPARATORS
        elif comp["type"] == cls._TAG_IDENTIFIER:
            valid_comparators = cls.VALID_TAG_COMPARATORS
        elif comp["type"] == cls._ATTRIBUTE_IDENTIFIER:
            if comp["key"] in cls.NUMERIC_ATTRIBUTES:
                valid_comparators = cls.VALID_NUMERIC_ATTRIBUTE_COMPARATORS
            else:
                valid_comparators = cls.VALID_STRING_ATTRIBUTE_COMPARATORS
        else:
            valid_comparators = set()

        if comparator not in valid_comparators:
            raise LumlFilterError(
                f"Invalid comparator '{comparator}' for {comp['type']} '{comp['key']}'. "
                f"Valid comparators are: {sorted(valid_comparators)}"
            )

        comp["comparator"] = comparator
        comp["value"] = cls._get_value(comp["type"], comp["key"], right)
        return comp

    @classmethod
    def parse_order_by(cls, order_by_str: str) -> tuple[str, str, bool]:
        """
        Parse an order_by string like 'name ASC' or 'metric.accuracy DESC'.

        Returns:
            (entity_type, key, is_ascending)
        """
        parts = order_by_str.strip().split()
        if len(parts) == 2 and parts[1].upper() in ("ASC", "DESC"):
            identifier_str = parts[0]
            is_ascending = parts[1].upper() == "ASC"
        elif len(parts) == 1:
            identifier_str = parts[0]
            is_ascending = True
        else:
            raise LumlFilterError(
                f"Invalid order_by clause '{order_by_str}'. "
                "Expected format: '<key> [ASC|DESC]'"
            )

        identifier = cls._get_identifier(
            identifier_str, cls.VALID_ORDER_BY_ATTRIBUTE_KEYS
        )
        return identifier["type"], identifier["key"], is_ascending

    @classmethod
    def parse_search_filter(cls, filter_string: str | None) -> list[dict]:
        """Parse a filter string into a list of comparison dicts."""
        if not filter_string:
            return []
        filter_string = cls._preprocess_filter(filter_string)
        try:
            parsed = sqlparse.parse(filter_string)
        except Exception as e:
            raise LumlFilterError(f"Error on parsing filter '{filter_string}'") from e
        if len(parsed) == 0 or not isinstance(parsed[0], Statement):
            raise LumlFilterError(
                f"Invalid filter '{filter_string}'. Could not be parsed."
            )
        if len(parsed) > 1:
            raise LumlFilterError(
                f"Search filter contained multiple expressions {filter_string!r}. "
                "Provide AND-ed expression list."
            )
        return cls._process_statement(parsed[0])

    @classmethod
    def _build_sql_filter(  # noqa: C901
        cls, parsed_filters: list[dict], dialect: str = "sqlite"
    ) -> tuple[str, list]:
        """
        Build a SQL WHERE clause from parsed filter dicts (may include operator dicts).

        Returns:
            (where_clause, params_list)
        """
        sql_parts: list[str] = []
        params: list[Any] = []

        for item in parsed_filters:
            if "operator" in item:
                sql_parts.append(item["operator"])
                continue

            if "group" in item:
                sub_sql, sub_params = cls._build_sql_filter(item["group"])
                sql_parts.append(f"({sub_sql})")
                params.extend(sub_params)
                continue

            key_type = item["type"]
            key = item["key"]
            value = item["value"]
            comparator = item["comparator"].upper()

            if key_type == cls._ATTRIBUTE_IDENTIFIER:
                if comparator == "IN":
                    placeholders = ",".join("?" * len(value))
                    sql_parts.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                elif comparator == "NOT IN":
                    placeholders = ",".join("?" * len(value))
                    sql_parts.append(f"{key} NOT IN ({placeholders})")
                    params.extend(value)
                elif comparator == "ILIKE":
                    sql_parts.append(f"UPPER({key}) LIKE UPPER(?)")
                    params.append(value)
                else:
                    sql_parts.append(f"{key} {comparator} ?")
                    params.append(value)

            elif key_type == cls._TAG_IDENTIFIER:
                # tags is a JSON array stored as text; match using LIKE on the serialized form
                if comparator == "ILIKE":
                    sql_parts.append("UPPER(tags) LIKE UPPER(?)")
                    params.append(value)
                else:
                    sql_parts.append(f"tags {comparator} ?")
                    params.append(value)

            elif key_type == cls._PARAM_IDENTIFIER:
                json_col = f"json_extract(static_params, '$.{key}')"
                if comparator == "ILIKE":
                    sql_parts.append(f"UPPER({json_col}) LIKE UPPER(?)")
                    params.append(value)
                else:
                    sql_parts.append(f"{json_col} {comparator} ?")
                    params.append(value)

            elif key_type == cls._METRIC_IDENTIFIER:
                json_col = f"json_extract(dynamic_params, '$.{key}')"
                sql_parts.append(f"{json_col} {comparator} ?")
                params.append(value)

        return " ".join(sql_parts), params

    @classmethod
    def _build_sql_order_by(cls, order_by_list: list[str]) -> str:
        """
        Build a SQL ORDER BY clause from a list of order_by strings.

        Returns:
            "ORDER BY col1 ASC, col2 DESC" or "" if order_by_list is empty.
        """
        if not order_by_list:
            return ""

        parts: list[str] = []
        for order_by_str in order_by_list:
            key_type, key, is_ascending = cls.parse_order_by(order_by_str)
            direction = "ASC" if is_ascending else "DESC"

            if key_type == cls._ATTRIBUTE_IDENTIFIER:
                parts.append(f"{key} {direction}")
            elif key_type == cls._PARAM_IDENTIFIER:
                parts.append(f"json_extract(static_params, '$.{key}') {direction}")
            elif key_type == cls._METRIC_IDENTIFIER:
                parts.append(f"json_extract(dynamic_params, '$.{key}') {direction}")
            else:
                raise LumlFilterError(f"Invalid order_by entity type '{key_type}'")

        return "ORDER BY " + ", ".join(parts)

    @classmethod
    def validate_filter_string(cls, filter_string: str | None) -> None:
        """
        Validate a filter string without executing it against the database.

        Raises:
            LumlFilterError: with a descriptive message if the filter string is invalid.

        Examples:
            validate_filter_string('name LIKE "%bert%"')   # OK, returns None
            validate_filter_string('nonexistent = "x"')    # raises LumlFilterError
            validate_filter_string('name LIKE "%a%" OR name LIKE "%b%"')  # OK, returns None
        """
        cls.parse_search_filter(filter_string)

    @classmethod
    def to_sql(
        cls,
        filter_string: str | None,
        order_by_list: list[str] | None = None,
    ) -> tuple[str, str, list]:
        """
        Parse filter_string and order_by_list into SQL clauses.

        Returns:
            (where_clause, order_by_clause, params)

        Examples:
            to_sql('name LIKE "%bert%"')
            → ('name LIKE ?', '', ['%bert%'])

            to_sql('status = "active"', ['created_at DESC'])
            → ('status = ?', 'ORDER BY created_at DESC', ['active'])

            to_sql('param.lr = 0.001')
            → ("json_extract(static_params, '$.lr') = ?", '', [0.001])

            to_sql('metric.accuracy > 0.9')
            → ("json_extract(dynamic_params, '$.accuracy') > ?", '', [0.9])
        """
        parsed_filters = cls.parse_search_filter(filter_string)
        where_clause, params = cls._build_sql_filter(parsed_filters)
        order_by_clause = cls._build_sql_order_by(order_by_list or [])
        return where_clause, order_by_clause, params


class SearchEvalsUtils(SearchUtils):
    """Filter evals with SQL-like syntax.

    Supported fields:
    - id, dataset_id                          → string ops: =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
    - created_at, updated_at                  → date ops:   =, !=, >, >=, <, <=  (ISO string)
    - inputs.<key>, outputs.<key>, refs.<key> → string or numeric ops based on value
    - scores.<key>, metadata.<key>            → string or numeric ops based on value

    Examples:
        outputs.prediction LIKE "%bert%"
        scores.accuracy > 0.9
        metadata.latency_ms >= 1000
        created_at > "2024-01-01"
        inputs.question CONTAINS "what"
        scores.accuracy > 0.8 AND metadata.latency_ms < 500
    """

    VALID_SEARCH_ATTRIBUTE_KEYS = {"id", "dataset_id", "created_at", "updated_at"}
    NUMERIC_ATTRIBUTES: set[str] = set()
    DATE_ATTRIBUTES = {"created_at", "updated_at"}
    STRING_ATTRIBUTES = {"id", "dataset_id"}
    JSON_COLUMNS = {"inputs", "outputs", "refs", "scores", "metadata"}

    _JSON_IDENTIFIER = "json"
    _ATTRIBUTE_IDENTIFIER = "attribute"

    VALID_STRING_ATTRIBUTE_COMPARATORS = {"=", "!=", "LIKE", "ILIKE", "IN", "NOT IN"}
    VALID_DATE_COMPARATORS = {"=", "!=", ">", ">=", "<", "<="}
    VALID_JSON_COMPARATORS = {
        "=",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "LIKE",
        "ILIKE",
        "IN",
        "NOT IN",
    }

    @classmethod
    def _get_identifier(cls, identifier_str: str, valid_attributes: set) -> dict:
        identifier_str = cls._trim_backticks(identifier_str.strip())
        parts = identifier_str.split(".", maxsplit=1)

        if len(parts) == 1:
            key = cls._trim_backticks(cls._strip_quotes(parts[0]))
            if key not in cls.VALID_SEARCH_ATTRIBUTE_KEYS:
                raise LumlFilterError(
                    f"Invalid attribute '{key}'. "
                    f"Valid attributes: {sorted(cls.VALID_SEARCH_ATTRIBUTE_KEYS)}. "
                    f"For JSON fields use: <column>.<key> where column is one of "
                    f"{sorted(cls.JSON_COLUMNS)}."
                )
            return {"type": cls._ATTRIBUTE_IDENTIFIER, "key": key}

        prefix, raw_key = parts
        key = cls._trim_backticks(cls._strip_quotes(raw_key))
        if prefix.lower() not in cls.JSON_COLUMNS:
            raise LumlFilterError(
                f"Invalid field prefix '{prefix}'. "
                f"Valid JSON columns: {sorted(cls.JSON_COLUMNS)}. "
                f"Valid bare attributes: {sorted(cls.VALID_SEARCH_ATTRIBUTE_KEYS)}."
            )
        return {"type": cls._JSON_IDENTIFIER, "column": prefix.lower(), "key": key}

    @classmethod
    def _get_value(cls, identifier_type: str, key: str, token: Token) -> Any:  # noqa: ANN401
        if identifier_type == cls._JSON_IDENTIFIER:
            if token.ttype in cls.NUMERIC_VALUE_TYPES:
                return float(token.value)
            if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
                return cls._strip_quotes(token.value, expect_quoted_value=True)
            if isinstance(token, Parenthesis):
                return cls._parse_list_from_sql_token(token)
            raise LumlFilterError(
                f"Expected string or numeric value for JSON field '{key}'. Got {token.value!r}"
            )

        # attribute
        if key in cls.DATE_ATTRIBUTES:
            if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
                return cls._strip_quotes(token.value, expect_quoted_value=True)
            if token.ttype in cls.NUMERIC_VALUE_TYPES:
                return token.value
            raise LumlFilterError(
                f"Expected ISO date string for '{key}'. Got {token.value!r}"
            )
        if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
            return cls._strip_quotes(token.value, expect_quoted_value=True)
        if isinstance(token, Parenthesis):
            return cls._parse_list_from_sql_token(token)
        raise LumlFilterError(
            f"Expected string value for attribute '{key}'. Got {token.value!r}"
        )

    @classmethod
    def _get_comparison(cls, comparison: Comparison) -> dict:
        stripped = [token for token in comparison.tokens if not token.is_whitespace]
        cls._validate_comparison(stripped)
        left, comparator_token, right = stripped
        comp = cls._get_identifier(left.value, cls.VALID_SEARCH_ATTRIBUTE_KEYS)
        comparator = comparator_token.value.upper()

        if comp["type"] == cls._JSON_IDENTIFIER:
            valid = cls.VALID_JSON_COMPARATORS
        elif comp["key"] in cls.DATE_ATTRIBUTES:
            valid = cls.VALID_DATE_COMPARATORS
        else:
            valid = cls.VALID_STRING_ATTRIBUTE_COMPARATORS

        if comparator not in valid:
            field = (
                f"{comp.get('column', '')}.{comp['key']}"
                if comp["type"] == cls._JSON_IDENTIFIER
                else comp["key"]
            )
            raise LumlFilterError(
                f"Invalid comparator '{comparator}' for '{field}'. "
                f"Valid comparators: {sorted(valid)}"
            )

        comp["comparator"] = comparator
        comp["value"] = cls._get_value(comp["type"], comp["key"], right)
        return comp

    @classmethod
    def _build_sql_filter(cls, parsed_filters: list[dict]) -> tuple[str, list]:  # noqa: C901
        sql_parts: list[str] = []
        params: list[Any] = []

        for item in parsed_filters:
            if "operator" in item:
                sql_parts.append(item["operator"])
                continue
            if "group" in item:
                sub_sql, sub_params = cls._build_sql_filter(item["group"])
                sql_parts.append(f"({sub_sql})")
                params.extend(sub_params)
                continue

            key_type = item["type"]
            key = item["key"]
            value = item["value"]
            comparator = item["comparator"].upper()

            if key_type == cls._JSON_IDENTIFIER:
                col = item["column"]
                expr = f"json_extract({col}, '$.{key}')"
                if comparator == "ILIKE":
                    sql_parts.append(f"UPPER({expr}) LIKE UPPER(?)")
                    params.append(value)
                elif comparator == "IN":
                    sql_parts.append(f"{expr} IN ({','.join('?' * len(value))})")
                    params.extend(value)
                elif comparator == "NOT IN":
                    sql_parts.append(f"{expr} NOT IN ({','.join('?' * len(value))})")
                    params.extend(value)
                else:
                    sql_parts.append(f"{expr} {comparator} ?")
                    params.append(value)
            else:
                if comparator == "ILIKE":
                    sql_parts.append(f"UPPER({key}) LIKE UPPER(?)")
                    params.append(value)
                elif comparator == "IN":
                    sql_parts.append(f"{key} IN ({','.join('?' * len(value))})")
                    params.extend(value)
                elif comparator == "NOT IN":
                    sql_parts.append(f"{key} NOT IN ({','.join('?' * len(value))})")
                    params.extend(value)
                else:
                    sql_parts.append(f"{key} {comparator} ?")
                    params.append(value)

        return " ".join(sql_parts), params

    @classmethod
    def parse_search_filter(cls, filter_string: str | None) -> list[dict]:
        if not filter_string:
            return []
        filter_string = cls._preprocess_filter(filter_string)
        try:
            parsed = sqlparse.parse(filter_string)
        except Exception as e:
            raise LumlFilterError(f"Error on parsing filter '{filter_string}'") from e
        if len(parsed) == 0 or not isinstance(parsed[0], Statement):
            raise LumlFilterError(
                f"Invalid filter '{filter_string}'. Could not be parsed."
            )
        if len(parsed) > 1:
            raise LumlFilterError(
                f"Search filter contained multiple expressions {filter_string!r}. "
                "Provide AND-ed expression list."
            )
        return cls._process_statement(parsed[0])

    @classmethod
    def validate_filter_string(cls, filter_string: str | None) -> None:
        cls.parse_search_filter(filter_string)

    @classmethod
    def to_sql(cls, filter_string: str | None) -> tuple[str, list]:  # type: ignore[override]
        """Parse filter_string into a SQL WHERE clause.

        Returns:
            (where_clause, params)

        Examples:
            to_sql('outputs.prediction LIKE "%bert%"')
            → ("json_extract(outputs, '$.prediction') LIKE ?", ['%bert%'])

            to_sql('scores.accuracy > 0.9 AND metadata.latency_ms < 500')
            → ("json_extract(scores, '$.accuracy') > ? AND json_extract(metadata, '$.latency_ms') < ?", [0.9, 500.0])

            to_sql('created_at > "2024-01-01"')
            → ('created_at > ?', ['2024-01-01'])
        """
        parsed = cls.parse_search_filter(filter_string)
        return cls._build_sql_filter(parsed)


class SearchTracesUtils(SearchUtils):
    """Filter traces by span attributes using SQL-like syntax.

    All filters operate on span attributes and are translated to a
    trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE ...) subquery.

    Supported syntax:
        attributes.<key> {op} <value>

    Operators:
        String values: =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
        Numeric values: =, !=, >, >=, <, <=

    Examples:
        attributes.http.method = "GET"
        attributes.http.status_code = 200
        attributes.db.statement CONTAINS "SELECT"
        attributes.http.status_code >= 400 AND attributes.http.status_code < 500
    """

    VALID_SEARCH_ATTRIBUTE_KEYS: set[str] = set()
    NUMERIC_ATTRIBUTES: set[str] = set()
    ATTRIBUTES_PREFIX = "attributes"
    _SPAN_ATTR_IDENTIFIER = "span_attribute"

    VALID_COMPARATORS = {
        "=",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "LIKE",
        "ILIKE",
        "IN",
        "NOT IN",
    }

    @classmethod
    def _get_identifier(cls, identifier_str: str, valid_attributes: set) -> dict:
        identifier_str = cls._trim_backticks(identifier_str.strip())
        parts = identifier_str.split(".", maxsplit=1)

        if len(parts) < 2 or parts[0].lower() != cls.ATTRIBUTES_PREFIX:
            raise LumlFilterError(
                f"Invalid field '{identifier_str}'. "
                "Trace filters must use the format: attributes.<key>  "
                f"(e.g. attributes.http.method, attributes.http.status_code)"
            )

        key = cls._trim_backticks(cls._strip_quotes(parts[1]))
        return {"type": cls._SPAN_ATTR_IDENTIFIER, "key": key}

    @classmethod
    def _get_value(cls, identifier_type: str, key: str, token: Token) -> Any:  # noqa: ANN401
        if token.ttype in cls.NUMERIC_VALUE_TYPES:
            return float(token.value)
        if token.ttype in cls.STRING_VALUE_TYPES or isinstance(token, Identifier):
            return cls._strip_quotes(token.value, expect_quoted_value=True)
        if isinstance(token, Parenthesis):
            return cls._parse_list_from_sql_token(token)
        raise LumlFilterError(
            f"Expected string or numeric value for attributes.{key}. Got {token.value!r}"
        )

    @classmethod
    def _get_comparison(cls, comparison: Comparison) -> dict:
        stripped = [token for token in comparison.tokens if not token.is_whitespace]
        cls._validate_comparison(stripped)
        left, comparator_token, right = stripped
        comp = cls._get_identifier(left.value, cls.VALID_SEARCH_ATTRIBUTE_KEYS)
        comparator = comparator_token.value.upper()

        if comparator not in cls.VALID_COMPARATORS:
            raise LumlFilterError(
                f"Invalid comparator '{comparator}' for 'attributes.{comp['key']}'. "
                f"Valid comparators: {sorted(cls.VALID_COMPARATORS)}"
            )

        comp["comparator"] = comparator
        comp["value"] = cls._get_value(comp["type"], comp["key"], right)
        return comp

    @classmethod
    def _build_inner_sql(cls, parsed_filters: list[dict]) -> tuple[str, list]:
        """Build the inner WHERE clause that runs against the spans table."""
        sql_parts: list[str] = []
        params: list[Any] = []

        for item in parsed_filters:
            if "operator" in item:
                sql_parts.append(item["operator"])
                continue
            if "group" in item:
                sub_sql, sub_params = cls._build_inner_sql(item["group"])
                sql_parts.append(f"({sub_sql})")
                params.extend(sub_params)
                continue

            key = item["key"]
            value = item["value"]
            comparator = item["comparator"].upper()
            expr = f"json_extract(attributes, '$.\"{key}\"')"

            if comparator == "ILIKE":
                sql_parts.append(f"UPPER({expr}) LIKE UPPER(?)")
                params.append(value)
            elif comparator == "IN":
                sql_parts.append(f"{expr} IN ({','.join('?' * len(value))})")
                params.extend(value)
            elif comparator == "NOT IN":
                sql_parts.append(f"{expr} NOT IN ({','.join('?' * len(value))})")
                params.extend(value)
            else:
                sql_parts.append(f"{expr} {comparator} ?")
                params.append(value)

        return " ".join(sql_parts), params

    @classmethod
    def parse_search_filter(cls, filter_string: str | None) -> list[dict]:
        if not filter_string:
            return []
        filter_string = cls._preprocess_filter(filter_string)
        try:
            parsed = sqlparse.parse(filter_string)
        except Exception as e:
            raise LumlFilterError(f"Error on parsing filter '{filter_string}'") from e
        if len(parsed) == 0 or not isinstance(parsed[0], Statement):
            raise LumlFilterError(
                f"Invalid filter '{filter_string}'. Could not be parsed."
            )
        if len(parsed) > 1:
            raise LumlFilterError(
                f"Search filter contained multiple expressions {filter_string!r}. "
                "Provide AND-ed expression list."
            )
        return cls._process_statement(parsed[0])

    @classmethod
    def validate_filter_string(cls, filter_string: str | None) -> None:
        cls.parse_search_filter(filter_string)

    @classmethod
    def to_sql(cls, filter_string: str | None) -> tuple[str, list]:  # type: ignore[override]
        """Parse filter_string into a trace_id subquery WHERE clause.

        Returns:
            (where_clause, params) — where_clause is a complete
            'trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE ...)' expression,
            or empty string if filter_string is None/empty.

        Examples:
            to_sql('attributes.http.method = "GET"')
            → ("trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE json_extract(attributes, '$.\"http.method\"') = ?)", ["GET"])

            to_sql('attributes.http.status_code >= 400 AND attributes.http.status_code < 500')
            → ("trace_id IN (...WHERE json_extract(attributes, '$.\"http.status_code\"') >= ? AND ... < ?)", [400.0, 500.0])
        """
        parsed = cls.parse_search_filter(filter_string)
        if not parsed:
            return "", []
        inner_sql, params = cls._build_inner_sql(parsed)
        return (
            f"trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE {inner_sql})",
            params,
        )
