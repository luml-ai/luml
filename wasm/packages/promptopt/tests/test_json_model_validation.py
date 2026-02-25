import pytest

from promptopt.dataclasses import Field, JsonModel


def test_validate_requires_all_fields() -> None:
    model = JsonModel([Field("name", "str"), Field("age", "int")])

    with pytest.raises(ValueError, match="Missing required fields"):
        model.validate({"name": "Alice"})


def test_validate_rejects_unexpected_fields() -> None:
    model = JsonModel([Field("name", "str")])

    with pytest.raises(ValueError, match="Unexpected fields"):
        model.validate({"name": "Alice", "extra": "value"})


def test_validate_enforces_scalar_types() -> None:
    model = JsonModel([Field("age", "int")])

    with pytest.raises(ValueError, match="must be of type int"):
        model.validate({"age": "10"})


def test_validate_rejects_bool_for_integer() -> None:
    model = JsonModel([Field("count", "integer")])

    with pytest.raises(ValueError, match="must be of type integer"):
        model.validate({"count": True})


def test_validate_enforces_enum_values() -> None:
    model = JsonModel([Field("status", "str", allowed_values=["open", "closed"])])

    with pytest.raises(ValueError, match="must be one of"):
        model.validate({"status": "unknown"})


def test_validate_variadic_requires_list_and_checks_item_types() -> None:
    model = JsonModel([Field("tags", "str", is_variadic=True)])

    with pytest.raises(ValueError, match="must be a list"):
        model.validate({"tags": "one"})

    with pytest.raises(ValueError, match="must be of type str"):
        model.validate({"tags": ["ok", 42]})

    assert model.validate({"tags": ["a", "b"]}) == {"tags": ["a", "b"]}
