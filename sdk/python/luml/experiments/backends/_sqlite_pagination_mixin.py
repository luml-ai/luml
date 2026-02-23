import json
import sqlite3
from typing import Any


class SQLitePaginationMixin:
    @staticmethod
    def _parse_value(v: Any) -> Any:  # noqa: ANN401
        if isinstance(v, str) and v and v[0] in ("{", "["):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return v
        return v

    @classmethod
    def _items_to_dict(
        cls, columns: list[str], rows: list[sqlite3.Row]
    ) -> list[dict[str, Any]]:
        return [
            {col: cls._parse_value(val) for col, val in zip(columns, row, strict=True)}
            for row in rows
        ]

    @staticmethod
    def _build_sort_expr(
        sort_by: str,
        json_sort_column: str | None,
        allowed_sort_columns: set[str] | None = None,
    ) -> str:
        if json_sort_column:
            return f"json_extract({json_sort_column}, '$.{sort_by}')"
        if allowed_sort_columns and sort_by not in allowed_sort_columns:
            sort_by = "created_at"
        return sort_by

    @classmethod
    def _build_cursor_clause(
        cls,
        sort_by: str,
        order: str,
        cursor_id: str | None,
        cursor_value: str | None,
        json_sort_column: str | None = None,
        allowed_sort_columns: set[str] | None = None,
    ) -> tuple[str, list[Any]]:
        if cursor_id is None:
            return "", []

        op = "<" if order == "desc" else ">"
        sort_expr = cls._build_sort_expr(
            sort_by, json_sort_column, allowed_sort_columns
        )

        if cursor_value is not None:
            clause = f"""
                WHERE ({sort_expr} {op} ?)
                   OR ({sort_expr} = ? AND id {op} ?)
            """
            return clause, [cursor_value, cursor_value, cursor_id]

        return f"WHERE id {op} ?", [cursor_id]

    def _execute_paginated_query(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: list[str],
        limit: int,
        sort_by: str,
        order: str,
        cursor_id: str | None = None,
        cursor_value: str | None = None,
        where: list[tuple[str, list[Any]]] | None = None,
        json_sort_column: str | None = None,
        allowed_sort_columns: set[str] | None = None,
    ) -> list[sqlite3.Row]:
        where_clause, params = self._build_cursor_clause(
            sort_by,
            order,
            cursor_id,
            cursor_value,
            json_sort_column,
            allowed_sort_columns,
        )

        if where:
            for clause, clause_params in where:
                if where_clause:
                    where_clause += f" AND ({clause})"
                else:
                    where_clause = f"WHERE ({clause})"
                params.extend(clause_params)

        sort_expr = self._build_sort_expr(
            sort_by, json_sort_column, allowed_sort_columns
        )
        null_order = "LAST" if order == "desc" else "FIRST"
        cols = ", ".join(columns)
        query = f"""
            SELECT {cols}
            FROM {table}
            {where_clause}
            ORDER BY {sort_expr} {order.upper()} NULLS {null_order}, id {order.upper()}
            LIMIT ?
        """
        params.append(limit + 1)

        db_cursor = conn.cursor()
        db_cursor.execute(query, params)
        return db_cursor.fetchall()

    @staticmethod
    def _sanitize_pagination_params(
        sort_by: str,
        order: str,
        allowed_sort_columns: set[str],
    ) -> tuple[str, str]:
        if sort_by not in allowed_sort_columns:
            sort_by = "created_at"
        order = order.lower()
        if order not in ("asc", "desc"):
            order = "desc"
        return sort_by, order
