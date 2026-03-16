import pytest

from luml.experiments.backends._cursor import Cursor


class TestCursor:
    def test_invalid_order_raises(self) -> None:
        with pytest.raises(ValueError, match="order must be 'asc' or 'desc'"):
            Cursor(id="x", value=1, order="bad")

    def test_valid_orders_accepted(self) -> None:
        Cursor(id="x", value=1, order="asc")
        Cursor(id="x", value=1, order="desc")

    def test_encode_decode_roundtrip_plain_value(self) -> None:
        cursor = Cursor(id="abc", value=42, sort_by="execution_time", order="asc")
        decoded = Cursor.decode(cursor.encode())
        assert decoded is not None
        assert decoded.id == "abc"
        assert decoded.value == 42
        assert decoded.sort_by == "execution_time"
        assert decoded.order == "asc"

    def test_encode_decode_roundtrip_datetime_value(self) -> None:
        from datetime import datetime

        dt = datetime(2024, 6, 1, 12, 0, 0)
        cursor = Cursor(id="abc", value=dt, sort_by="created_at", order="desc")
        encoded = cursor.encode()
        decoded = Cursor.decode(encoded)
        assert decoded is not None
        assert decoded.value == dt

    def test_decode_none_returns_none(self) -> None:
        assert Cursor.decode(None) is None

    def test_decode_empty_string_returns_none(self) -> None:
        assert Cursor.decode("") is None

    def test_decode_corrupt_string_returns_none(self) -> None:
        assert Cursor.decode("not-valid-base64!!!!garbage") is None

    def test_decode_valid_base64_but_wrong_structure_returns_none(self) -> None:
        import base64
        import json

        bad = base64.urlsafe_b64encode(json.dumps({"key": "val"}).encode()).decode()
        assert Cursor.decode(bad) is None

    def test_validate_for_matching_sort_and_order_returns_self(self) -> None:
        cursor = Cursor(id="x", value=1, sort_by="name", order="asc")
        assert cursor.validate_for("name", "asc") is cursor

    def test_validate_for_different_sort_returns_none(self) -> None:
        cursor = Cursor(id="x", value=1, sort_by="name", order="asc")
        assert cursor.validate_for("created_at", "asc") is None

    def test_validate_for_different_order_returns_none(self) -> None:
        cursor = Cursor(id="x", value=1, sort_by="name", order="asc")
        assert cursor.validate_for("name", "desc") is None

    def test_build_returns_none_when_items_lte_limit(self) -> None:
        items = [type("R", (), {"id": str(i), "created_at": None})() for i in range(3)]
        assert Cursor.build(items, limit=3) is None
        assert Cursor.build(items, limit=5) is None

    def test_build_returns_cursor_for_last_item_on_page(self) -> None:
        from datetime import datetime

        class Rec:
            def __init__(self, i: int) -> None:
                self.id = str(i)
                self.created_at = datetime(2024, 1, i + 1)

        items = [Rec(i) for i in range(5)]
        cursor = Cursor.build(items, limit=3)
        assert cursor is not None
        assert cursor.id == items[2].id

    def test_build_with_json_sort_column_extracts_nested_value(self) -> None:
        class Rec:
            def __init__(self, i: int) -> None:
                self.id = str(i)
                self.dynamic_metrics = {"score": i * 10}

        items = [Rec(i) for i in range(4)]
        cursor = Cursor.build(
            items, limit=3, sort_by="score", json_sort_column="dynamic_metrics"
        )
        assert cursor is not None
        assert cursor.value == 20  # items[2].dynamic_metrics["score"]

    def test_build_with_json_sort_column_none_field_gives_none_value(self) -> None:
        class Rec:
            def __init__(self, i: int) -> None:
                self.id = str(i)
                self.dynamic_metrics = None

        items = [Rec(i) for i in range(4)]
        cursor = Cursor.build(
            items, limit=3, sort_by="score", json_sort_column="dynamic_metrics"
        )
        assert cursor is not None
        assert cursor.value is None

    def test_get_cursor_returns_encoded_string_when_has_next(self) -> None:
        class Rec:
            def __init__(self, i: int) -> None:
                self.id = str(i)
                self.created_at = None

        items = [Rec(i) for i in range(4)]
        result = Cursor.get_cursor(items, limit=3)
        assert isinstance(result, str)

    def test_get_cursor_returns_none_when_no_next(self) -> None:
        class Rec:
            def __init__(self, i: int) -> None:
                self.id = str(i)
                self.created_at = None

        items = [Rec(i) for i in range(2)]
        assert Cursor.get_cursor(items, limit=3) is None

    def test_decode_and_validate_returns_cursor_when_matches(self) -> None:
        cursor = Cursor(id="x", value=5, sort_by="name", order="asc")
        encoded = cursor.encode()
        result = Cursor.decode_and_validate(encoded, sort_by="name", order="asc")
        assert result is not None
        assert result.id == "x"

    def test_decode_and_validate_returns_none_when_mismatch(self) -> None:
        cursor = Cursor(id="x", value=5, sort_by="name", order="asc")
        encoded = cursor.encode()
        assert Cursor.decode_and_validate(encoded, sort_by="name", order="desc") is None

    def test_decode_and_validate_returns_none_for_none_input(self) -> None:
        assert Cursor.decode_and_validate(None, sort_by="name", order="asc") is None
